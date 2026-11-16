"""DB-API faults only; these tests do not qualify a SQL Server engine."""
import hashlib
from types import SimpleNamespace
import pytest

from src.persistence.azure_sql.attestation_journal import AzureSqlAttestationJournal


class Database:
    def __init__(self):
        self.rows, self.connections, self.statements = {}, [], []
        self.commit_mode, self.autocommit, self.fail_read = "normal", False, False
        self.rollbacks = 0
    def connect(self):
        c=Connection(self);self.connections.append(c);return c


class Connection:
    def __init__(self,db):
        self.db,self.pending,self.autocommit,self.closed=db,{},db.autocommit,False
    def cursor(self):return Cursor(self)
    def commit(self):
        if self.db.commit_mode=="before":raise ConnectionError("unknown before")
        assert not set(self.pending)&set(self.db.rows)
        self.db.rows.update(self.pending);self.pending={}
        if self.db.commit_mode=="after":raise ConnectionError("ack lost")
    def rollback(self):self.db.rollbacks+=1;self.pending={}
    def close(self):self.closed=True


class Cursor:
    def __init__(self,c):self.c,self.results=c,[]
    def execute(self,sql,p):
        d=self.c.db;d.statements.append((sql,dict(p)))
        assert all(word not in sql.upper() for word in ("UPDATE ","DELETE ","MERGE ","CREATE "))
        if sql.startswith("INSERT"):
            if p["claim"] in d.rows or p["claim"] in self.c.pending:raise RuntimeError("unclassified")
            self.c.pending[p["claim"]]=(p["owner"],p["digest"],p["record"])
        else:
            if d.fail_read:raise ConnectionError("private read error")
            self.results=[d.rows[p["claim"]]] if p["claim"] in d.rows else []
    def fetchone(self):return self.results.pop(0) if self.results else None
    def close(self):pass


def fixture():
    db=Database()
    return db,AzureSqlAttestationJournal(connection_factory=db.connect,read_connection_factory=db.connect)


def test_all_claims_committed_atomically_then_separate_readback():
    db,j=fixture();keys=("a"*64,"b"*64,"c"*64)
    assert j.reserve(keys,keys[0],b'{"private":"record"}') is True
    assert len(db.rows)==3 and len(db.connections)==4 and all(c.closed for c in db.connections)
    assert j.read_claim(keys[0])==b'{"private":"record"}'
    assert not j.reserve(keys,keys[0],b'{"private":"record"}')
    assert len(db.rows)==3 and db.rollbacks==1


@pytest.mark.parametrize("mode,rows",[("before",0),("after",2)])
def test_unknown_commit_never_grants_ownership_or_retries(mode,rows):
    db,j=fixture();db.commit_mode=mode
    assert not j.reserve(("a"*64,"b"*64),"a"*64,b"private")
    assert len(db.rows)==rows and len(db.statements)==2 and db.rollbacks==0
    # An explicit recovery read reports bytes, never grants a run token.
    assert j.read_claim("a"*64)==(b"private" if rows else None)
    assert sum(s.startswith("INSERT") for s,p in db.statements)==2


def test_overlap_rolls_back_all_new_claims_without_duplicate_classification():
    db,j=fixture();assert j.reserve(("b"*64,),"b"*64,b"first")
    assert not j.reserve(("a"*64,"b"*64),"a"*64,b"second")
    assert set(db.rows)=={bytes.fromhex("b"*64)}
    assert db.rollbacks==1


@pytest.mark.parametrize("fault",["autocommit","fail_read"])
def test_autocommit_or_read_failure_cannot_grant_ownership(fault):
    db,j=fixture();setattr(db,fault,True)
    assert not j.reserve(("a"*64,),"a"*64,b"record")


def test_journal_stage_cannot_be_overwritten_and_readback_is_exact():
    db,j=fixture();owner="a"*64
    assert j.put(owner,"PAIR_0",b'{"record":1}')
    assert j.get(owner,"PAIR_0")==b'{"record":1}'
    assert not j.put(owner,"PAIR_0",b'{"record":2}')
    assert j.get(owner,"PAIR_0")==b'{"record":1}'
    before=len(db.statements)
    assert j.get(owner,"PAIR_1") is None
    assert not db.statements[before][0].startswith("INSERT")


@pytest.mark.parametrize("bad",[b"",b"x"*1048577,"text",None],
                         ids=["empty-bytes","over-limit-bytes","wrong-type-text","none"])
def test_invalid_private_record_never_opens_connection(bad):
    db,j=fixture()
    with pytest.raises(ValueError):j.reserve(("a"*64,),"a"*64,bad)
    assert not db.connections


@pytest.mark.parametrize("keys",[(),("a"*64,"a"*64),("../other",),tuple(str(n)*64 for n in range(9))])
def test_invalid_claims_rejected_before_connection(keys):
    db,j=fixture()
    with pytest.raises(ValueError):j.reserve(keys,"a"*64,b"record")
    assert not db.connections


def test_tampered_journal_record_is_not_read_back():
    db,j=fixture();assert j.put("a"*64,"PAIR_0",b"record")
    key=next(iter(db.rows));owner,digest,raw=db.rows[key]
    db.rows[key]=(owner,digest,b"changed")
    with pytest.raises(ValueError):j.get("a"*64,"PAIR_0")


def test_unknown_stage_is_rejected_before_io():
    db,j=fixture()
    with pytest.raises(ValueError):j.put("a"*64,"FORGED",b"x")
    assert not db.connections
