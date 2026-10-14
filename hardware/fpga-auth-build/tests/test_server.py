"""Software tests with synthetic transport; these are NOT physical PUF results."""
import importlib.util,contextlib,io,hashlib,csv,tempfile,shutil
from pathlib import Path
from types import SimpleNamespace

root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('server',root/'server.py')
s=importlib.util.module_from_spec(spec); spec.loader.exec_module(s)
class Link:
 def __init__(self,identity='A',failed=False,mode='PUF'):
  self.identity=identity;self.failed=failed;self.mode=mode
 def command(self,line):
  p=line.split()
  if p[0]=='PING':return f'OK PING {self.mode} 64'
  if p[0]=='VERDICT':return 'OK VERDICT'
  if p[0]=='READ':
   if self.failed:raise TimeoutError('synthetic link failure')
   bit=hashlib.sha256((self.identity+p[1]).encode()).digest()[0]&1
   return f'OK READ {p[1]} '+str(bit)*int(p[2])
  raise ValueError(line)

scratch=Path(tempfile.mkdtemp(prefix='puf-server-check-'))
dbfile=scratch/'test.sqlite'
if dbfile.exists():dbfile.unlink()
db=s.database(dbfile)
bitstream=scratch/'synthetic-not-hardware.fs';bitstream.write_bytes(b'TEST ONLY; NOT FPGA CONFIGURATION')
def quiet(fn,*args):
 with contextlib.redirect_stdout(io.StringIO()) as buffer:fn(*args)
 return buffer.getvalue()
args=SimpleNamespace(device='FPGA_A',condition='SYNTHETIC SOFTWARE TEST',
 challenges=512,repeats=3,min_agreement=3,bitstream=str(bitstream))
quiet(s.enroll,db,Link(),args)
assert db.execute('SELECT COUNT(*) FROM crps').fetchone()[0]==512
assert db.execute('SELECT COUNT(*) FROM samples').fetchone()[0]==1536
auth=SimpleNamespace(device='FPGA_A',condition='SYNTHETIC SOFTWARE TEST',bits=128,repeats=7,max_errors=6)
quiet(s.authenticate,db,Link('A'),auth)
assert db.execute("SELECT state,mismatches FROM sessions WHERE mode='AUTH' ORDER BY rowid DESC LIMIT 1").fetchone()[:]==('ACCEPT',0)
quiet(s.authenticate,db,Link('B'),auth)
row=db.execute("SELECT state,mismatches FROM sessions WHERE mode='AUTH' ORDER BY rowid DESC LIMIT 1").fetchone()
assert row['state']=='REJECT' and row['mismatches']>6
before=db.execute('SELECT COUNT(*) FROM crps WHERE used=1').fetchone()[0]
try:quiet(s.authenticate,db,Link(failed=True),auth)
except TimeoutError:pass
else:raise AssertionError('Failure was accepted')
after=db.execute('SELECT COUNT(*) FROM crps WHERE used=1').fetchone()[0]
assert after-before==128
assert db.execute("SELECT state FROM sessions ORDER BY rowid DESC LIMIT 1").fetchone()[0]=='ERROR'
remaining=db.execute('SELECT COUNT(*) FROM crps WHERE used=0').fetchone()[0]
try:s.reserve(db,'FPGA_A',remaining+1)
except ValueError:pass
else:raise AssertionError('Exhausted pool accepted')
assert db.execute('SELECT COUNT(*) FROM crps WHERE used=0').fetchone()[0]==remaining
try:s.require_puf(Link(mode='LINK_ONLY'))
except RuntimeError:pass
else:raise AssertionError('Loopback enrolled as PUF')
class Malformed(Link):
 def command(self,line):return 'OK READ 0000000000000000 1111111'
try:s.read_bits(Malformed(),'0123456789ABCDEF',7)
except RuntimeError:pass
else:raise AssertionError('Wrong echoed challenge accepted')
char=SimpleNamespace(device='FPGA_A',condition='SYNTHETIC LATER MEASUREMENT',challenges=32,repeats=7)
quiet(s.characterize,db,Link(),char)
assert db.execute("SELECT mismatches FROM sessions WHERE mode='CHARACTERIZE'").fetchone()[0]==0
changed=SimpleNamespace(**vars(args));changed.bitstream=str(scratch/'changed.fs')
Path(changed.bitstream).write_bytes(b'DIFFERENT')
try:quiet(s.enroll,db,Link(),changed)
except ValueError:pass
else:raise AssertionError('Different bitstream silently re-enrolled')
quiet(s.export,db,scratch/'csv')
assert len(list((scratch/'csv').glob('*.csv')))==4
with (scratch/'csv'/'crps.csv').open() as f:
 records=list(csv.DictReader(f));assert len(records)==512
 assert all(len(row['challenge'])==16 for row in records)
db.close()
print('PASS: enrollment, raw records, genuine/impostor decision, challenge consumption,')
print('      failure recording, exhaustion rollback, link-only rejection, echo validation,')
print('      later characterization, bitstream mismatch handling, CSV export.')

shutil.rmtree(scratch)
