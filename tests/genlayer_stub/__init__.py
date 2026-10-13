import copy
import types
import typing

__all__ = ["gl", "Address", "TreeMap", "DynArray", "u256", "i256", "allow_storage"]


class Address:
    def __init__(self, value):
        if isinstance(value, Address):
            text = value._hex
        elif isinstance(value, (bytes, bytearray)):
            text = "0x" + bytes(value).hex()
        else:
            text = str(value)
        text = text.lower()
        if not (text.startswith("0x") and len(text) == 42 and all(c in "0123456789abcdef" for c in text[2:])):
            raise ValueError("invalid address: " + text)
        self._hex = text

    @property
    def as_hex(self):
        return self._hex

    def __eq__(self, other):
        return isinstance(other, Address) and other._hex == self._hex

    def __hash__(self):
        return hash(self._hex)

    def __repr__(self):
        return "Address(" + self._hex + ")"


class u256(int):
    def __new__(cls, value=0):
        value = int(value)
        if value < 0 or value >= 2**256:
            raise OverflowError("u256 out of range")
        return super().__new__(cls, value)


class i256(int):
    pass


class TreeMap(dict):
    def __class_getitem__(cls, params):
        return types.GenericAlias(cls, params if isinstance(params, tuple) else (params,))


class DynArray(list):
    def __class_getitem__(cls, params):
        return types.GenericAlias(cls, params if isinstance(params, tuple) else (params,))


def allow_storage(cls):
    return cls


class _State:
    def __init__(self):
        self.reset()

    def reset(self):
        self.msg = None
        self.web = {}
        self.validator_web = None
        self.llm = lambda prompt: {"verdict": "SUPPORTED", "reason": "stub"}
        self.validator_llm = None
        self.prompts = []
        self.validators = 3
        self.role = "leader"
        self.pending_transfers = []
        self.nondet_calls = 0


STATE = _State()


class _Message:
    def __init__(self, sender, value):
        self.sender_address = sender
        self.value = value


def _mark(kind, payable=False):
    def decorate(fn):
        fn._gl_kind = kind
        fn._gl_payable = payable
        return fn

    return decorate


class _Write:
    def __call__(self, fn):
        return _mark("write")(fn)

    payable = staticmethod(_mark("write", True))


class _Public:
    view = staticmethod(_mark("view"))
    write = _Write()


def _annotations(cls):
    merged = {}
    for klass in reversed(cls.__mro__):
        merged.update(getattr(klass, "__annotations__", {}))
    return merged


class _ContractBase:
    def __setattr__(self, name, value):
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        declared = _annotations(type(self))
        if name not in declared:
            raise AssertionError("undeclared storage field: " + name)
        annotation = declared[name]
        origin = typing.get_origin(annotation)
        if origin is TreeMap and not isinstance(value, TreeMap):
            raise AssertionError("Is right the same storage type? TreeMap <- " + type(value).__name__)
        if origin is DynArray:
            if not isinstance(value, list):
                raise AssertionError("DynArray needs a list")
            value = DynArray(value)
        if annotation is u256 and not isinstance(value, u256):
            raise TypeError("u256 field needs a u256 value, got " + type(value).__name__)
        object.__setattr__(self, name, value)

    @property
    def balance(self):
        return self._balance


class _Proxy:
    def __init__(self, address):
        self.address = address

    def emit_transfer(self, *, value, on=None):
        if on is not None:
            raise SystemError("2: inval")
        STATE.pending_transfers.append((self.address, int(value)))


class Return:
    def __init__(self, calldata):
        self.calldata = calldata


class _VM:
    Return = Return

    def run_nondet_unsafe(self, leader_fn, validator_fn, /):
        for fn in (leader_fn, validator_fn):
            for cell in fn.__closure__ or ():
                if isinstance(cell.cell_contents, _ContractBase):
                    raise RuntimeError("nondet closure captures contract storage")
        STATE.nondet_calls += 1
        STATE.role = "leader"
        try:
            result = leader_fn()
        finally:
            STATE.role = "leader"
        for _ in range(STATE.validators):
            STATE.role = "validator"
            try:
                ok = validator_fn(Return(result))
            except Exception:
                ok = False
            finally:
                STATE.role = "leader"
            if not isinstance(ok, bool):
                raise TypeError("validator_fn must return bool")
            if not ok:
                raise Exception("Undetermined: validators did not agree")
        return result


class _Web:
    def render(self, url, mode="text"):
        sources = STATE.web
        if STATE.role == "validator" and STATE.validator_web is not None:
            sources = STATE.validator_web
        page = sources.get(url)
        if page is None:
            raise Exception("WEBPAGE_LOAD_FAILED 404")
        if isinstance(page, Exception):
            raise page
        return page


class _Nondet:
    web = _Web()

    def exec_prompt(self, prompt, response_format=None):
        STATE.prompts.append(prompt)
        handler = STATE.llm
        if STATE.role == "validator" and STATE.validator_llm is not None:
            handler = STATE.validator_llm
        out = handler(prompt)
        if isinstance(out, Exception):
            raise out
        return out


class _GL:
    Contract = _ContractBase
    public = _Public()
    vm = _VM()
    nondet = _Nondet()

    @property
    def message(self):
        if STATE.msg is None:
            raise RuntimeError("no message in this context")
        return STATE.msg

    def get_contract_at(self, address):
        return _Proxy(address)


gl = _GL()


class Env:
    def __init__(self):
        STATE.reset()
        self.transfers = []
        self.total_in = 0

    @property
    def web(self):
        return STATE.web

    def deploy(self, cls, sender, *args):
        inst = cls.__new__(cls)
        object.__setattr__(inst, "_balance", 0)
        for name, annotation in _annotations(cls).items():
            origin = typing.get_origin(annotation)
            if origin is TreeMap:
                object.__setattr__(inst, name, TreeMap())
            elif origin is DynArray:
                object.__setattr__(inst, name, DynArray())
            elif annotation is u256:
                object.__setattr__(inst, name, u256(0))
        STATE.msg = _Message(Address(sender), u256(0))
        try:
            cls.__init__(inst, *args)
        finally:
            STATE.msg = None
        return Deployment(inst, self)


class Deployment:
    def __init__(self, inst, env):
        self.inst = inst
        self.env = env

    def tx(self, sender, name, *args, value=0):
        fn = getattr(type(self.inst), name)
        if getattr(fn, "_gl_kind", None) != "write":
            raise AssertionError(name + " is not a write method")
        if value and not fn._gl_payable:
            raise Exception("non-payable method received value")
        snapshot = copy.deepcopy({k: v for k, v in self.inst.__dict__.items() if k != "_balance"})
        STATE.msg = _Message(Address(sender), u256(value))
        STATE.pending_transfers = []
        self.inst._balance += value
        self.env.total_in += value
        try:
            result = fn(self.inst, *args)
        except BaseException:
            balance = self.inst._balance
            self.inst.__dict__.clear()
            self.inst.__dict__.update(snapshot)
            self.inst.__dict__["_balance"] = balance
            STATE.pending_transfers = []
            raise
        finally:
            STATE.msg = None
        for address, amount in STATE.pending_transfers:
            if amount > self.inst._balance:
                raise AssertionError("contract tried to send more than its balance")
            self.inst._balance -= amount
            self.env.transfers.append((address, amount))
        STATE.pending_transfers = []
        return result

    def view(self, name, *args):
        fn = getattr(type(self.inst), name)
        if getattr(fn, "_gl_kind", None) != "view":
            raise AssertionError(name + " is not a view method")
        before = copy.deepcopy(self.inst.__dict__)
        result = fn(self.inst, *args)
        if before != self.inst.__dict__:
            raise AssertionError("view method mutated storage: " + name)
        return result
