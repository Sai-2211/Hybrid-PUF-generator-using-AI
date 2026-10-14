#!/usr/bin/env python3
"""Local laboratory server for actual USB PUF measurements, no network listener."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import secrets
import sqlite3
import time
from datetime import datetime, timezone

def now(): return datetime.now(timezone.utc).isoformat()

def challenge_hex(text):
    text=str(text).upper()
    if len(text)!=16 or any(c not in '0123456789ABCDEF' for c in text):
        raise ValueError('Challenge needs exactly 16 hexadecimal digits')
    return text

class HardwareLink:
    def __init__(self,port):
        import serial
        self.serial=serial.Serial(port,115200,timeout=.25,write_timeout=2)
        time.sleep(1.5); self.serial.reset_input_buffer()
    def close(self): self.serial.close()
    def command(self,text):
        self.serial.write((text+'\n').encode('ascii')); self.serial.flush()
        deadline=time.monotonic()+10; received=bytearray()
        while time.monotonic()<deadline:
            value=self.serial.read(1)
            if not value: continue
            if value==b'\n':
                reply=received.decode('ascii').strip()
                if reply.startswith('ERR '): raise RuntimeError(reply)
                if not reply.startswith('OK '): raise RuntimeError('Unexpected reply: '+reply)
                return reply
            received.extend(value)
            if len(received)>128: raise RuntimeError('Reply exceeded protocol limit')
        raise TimeoutError('No complete ESP reply within 10 seconds')

def read_bits(link,challenge,repeats):
    challenge=challenge_hex(challenge)
    parts=link.command(f'READ {challenge} {repeats}').split()
    if len(parts)!=4 or parts[:2]!=['OK','READ'] or parts[2]!=challenge:
        raise RuntimeError('Reply does not match requested challenge')
    bits=parts[3]
    if len(bits)!=repeats or set(bits)-{'0','1'}: raise RuntimeError('Invalid response bits')
    return bits

def require_puf(link):
    if link.command('PING')!='OK PING PUF 64':
        raise RuntimeError('FPGA is in link-only mode; PUF measurements disabled')

def database(path):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path); db.row_factory=sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''
    CREATE TABLE IF NOT EXISTS devices(id TEXT PRIMARY KEY,hash TEXT NOT NULL,created TEXT);
    CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,mode TEXT,device TEXT,
      created TEXT,condition TEXT,state TEXT,bits INTEGER,mismatches INTEGER,
      threshold INTEGER,elapsed_ms REAL,error TEXT);
    CREATE TABLE IF NOT EXISTS crps(id INTEGER PRIMARY KEY,device TEXT REFERENCES devices(id),
      challenge TEXT,expected INTEGER,ones INTEGER,trials INTEGER,consistency REAL,
      eligible INTEGER,used INTEGER DEFAULT 0,UNIQUE(device,challenge));
    CREATE TABLE IF NOT EXISTS samples(id INTEGER PRIMARY KEY,session TEXT REFERENCES sessions(id),
      device TEXT,challenge TEXT,trial INTEGER,response INTEGER,created TEXT);
    ''')
    return db

def new_session(db,mode,device,condition):
    session=secrets.token_hex(16)
    db.execute('INSERT INTO sessions(id,mode,device,created,condition,state) VALUES(?,?,?,?,?,?)',
               (session,mode,device,now(),condition,'IN_PROGRESS'))
    db.commit(); return session

def finish(db,session,state,started,**fields):
    if set(fields)-{'bits','mismatches','threshold','error'}: raise ValueError('Bad session fields')
    fields.update(state=state,elapsed_ms=(time.monotonic()-started)*1000)
    db.execute('UPDATE sessions SET '+','.join(k+'=?' for k in fields)+' WHERE id=?',
               (*fields.values(),session)); db.commit()

def save_samples(db,session,device,challenge,bits):
    stamp=now()
    db.executemany('INSERT INTO samples(session,device,challenge,trial,response,created) '
                   'VALUES(?,?,?,?,?,?)',
                   [(session,device,challenge,i+1,int(bit),stamp) for i,bit in enumerate(bits)])

def enroll(db,link,args):
    require_puf(link)
    digest=hashlib.sha256(Path(args.bitstream).read_bytes()).hexdigest()
    row=db.execute('SELECT * FROM devices WHERE id=?',(args.device,)).fetchone()
    if row and row['hash']!=digest: raise ValueError('Different bitstream: use a new device ID')
    if not row:
        db.execute('INSERT INTO devices VALUES(?,?,?)',(args.device,digest,now())); db.commit()
    session=new_session(db,'ENROLL',args.device,args.condition); started=time.monotonic()
    eligible=ones_total=0
    try:
        for i in range(args.challenges):
            while True:
                challenge=f'{secrets.randbits(64):016X}'
                if not db.execute('SELECT 1 FROM crps WHERE device=? AND challenge=?',
                                  (args.device,challenge)).fetchone(): break
            bits=read_bits(link,challenge,args.repeats)
            ones=bits.count('1'); majority=int(ones>args.repeats//2)
            agreement=max(ones,args.repeats-ones); good=int(agreement>=args.min_agreement)
            save_samples(db,session,args.device,challenge,bits)
            db.execute('INSERT INTO crps(device,challenge,expected,ones,trials,consistency,eligible) '
                       'VALUES(?,?,?,?,?,?,?)',(args.device,challenge,majority,ones,
                       args.repeats,agreement/args.repeats,good)); db.commit()
            eligible+=good; ones_total+=majority
            if (i+1)%100==0: print(f'Recorded {i+1}/{args.challenges}',flush=True)
        finish(db,session,'COMPLETE',started,bits=args.challenges)
        print(json.dumps(dict(session=session,enrolled=args.challenges,eligible=eligible,
              reference_ones_percent=100*ones_total/args.challenges,bitstream_sha256=digest),indent=2))
        print('Validate preliminary enrollment consistency with separate later measurements.')
    except BaseException as error:
        finish(db,session,'ERROR',started,error=str(error)); raise

def reserve(db,device,count):
    # Consumed BEFORE exposure and never recycled after failure.
    db.execute('BEGIN IMMEDIATE')
    try:
        pool=db.execute('SELECT * FROM crps WHERE device=? AND eligible=1 AND used=0',(device,)).fetchall()
        if len(pool)<count: raise ValueError(f'Need {count} unused CRPs; only {len(pool)} remain')
        rows=secrets.SystemRandom().sample(pool,count)
        db.executemany('UPDATE crps SET used=1 WHERE id=?',[(r['id'],) for r in rows])
        db.commit(); return rows
    except BaseException: db.rollback(); raise

def authenticate(db,link,args):
    require_puf(link)
    if not db.execute('SELECT 1 FROM devices WHERE id=?',(args.device,)).fetchone():
        raise ValueError('Device is not enrolled')
    rows=reserve(db,args.device,args.bits)
    session=new_session(db,'AUTH',args.device,args.condition); started=time.monotonic()
    errors=0
    try:
        for row in rows:
            bits=read_bits(link,row['challenge'],args.repeats)
            save_samples(db,session,args.device,row['challenge'],bits); db.commit()
            errors+=int(bits.count('1')>args.repeats//2)!=row['expected']
        decision='ACCEPT' if errors<=args.max_errors else 'REJECT'
        finish(db,session,decision,started,bits=args.bits,mismatches=errors,threshold=args.max_errors)
    except BaseException as error:
        finish(db,session,'ERROR',started,bits=args.bits,error=str(error))
        try: link.command('VERDICT 0')
        except Exception: pass
        raise
    display_error=None
    try:
        if link.command('VERDICT '+str(int(decision=='ACCEPT')))!='OK VERDICT':
            raise RuntimeError('Unexpected display acknowledgement')
    except Exception as error: display_error=str(error)
    print(json.dumps(dict(session=session,decision=decision,bits=args.bits,mismatches=errors,
          threshold=args.max_errors,elapsed_ms=round((time.monotonic()-started)*1000,1),
          display_error=display_error),indent=2))

def characterize(db,link,args):
    require_puf(link)
    rows=db.execute('SELECT * FROM crps WHERE device=? ORDER BY id LIMIT ?',
                    (args.device,args.challenges)).fetchall()
    if not rows: raise ValueError('No enrolled challenges')
    db.executemany('UPDATE crps SET used=1 WHERE id=?',[(r['id'],) for r in rows]); db.commit()
    session=new_session(db,'CHARACTERIZE',args.device,args.condition); started=time.monotonic(); errors=0
    try:
        for row in rows:
            bits=read_bits(link,row['challenge'],args.repeats)
            save_samples(db,session,args.device,row['challenge'],bits); db.commit()
            errors+=sum(int(b)!=row['expected'] for b in bits)
        total=len(rows)*args.repeats
        finish(db,session,'COMPLETE',started,bits=total,mismatches=errors)
        print(json.dumps(dict(session=session,raw_bits=total,mismatches=errors,
              raw_reference_match_percent=100*(1-errors/total)),indent=2))
    except BaseException as error:
        finish(db,session,'ERROR',started,error=str(error)); raise

def export(db,directory):
    directory=Path(directory); directory.mkdir(parents=True,exist_ok=True)
    for table in ('devices','crps','samples','sessions'):
        cursor=db.execute('SELECT * FROM '+table)
        with (directory/(table+'.csv')).open('w',newline='',encoding='utf-8') as f:
            writer=csv.writer(f); writer.writerow([c[0] for c in cursor.description]); writer.writerows(cursor)
    print('Saved four CSV files in',directory.resolve())

def parser():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--db',default='records/auth.sqlite')
    sub=p.add_subparsers(dest='action',required=True); sub.add_parser('ports')
    a=sub.add_parser('export'); a.add_argument('--directory',default='records/csv')
    for action in ('ping','loop','probe','enroll','auth','characterize'):
        a=sub.add_parser(action); a.add_argument('--port',required=True)
        if action in ('loop','probe'): a.add_argument('--challenge',required=True,type=challenge_hex)
        if action in ('probe','enroll','auth','characterize'):
            a.add_argument('--repeats',type=int,choices=range(1,32,2),default=31 if action=='enroll' else 7)
        if action in ('enroll','auth','characterize'):
            a.add_argument('--device',required=True)
            a.add_argument('--condition',default='ambient; temperature and voltage not measured')
        if action in ('enroll','characterize'):
            a.add_argument('--challenges',type=int,default=1024 if action=='enroll' else 128)
        if action=='enroll':
            a.add_argument('--bitstream',required=True); a.add_argument('--min-agreement',type=int,default=30)
        if action=='auth':
            a.add_argument('--bits',type=int,default=128); a.add_argument('--max-errors',type=int,default=6)
    return p

def main():
    args=parser().parse_args()
    if args.action=='ports':
        from serial.tools import list_ports
        for port in list_ports.comports(): print(port.device,'—',port.description)
        return
    if hasattr(args,'challenges') and not 1<=args.challenges<=100000: raise ValueError('Invalid challenge count')
    if args.action=='enroll' and not 1<=args.min_agreement<=args.repeats: raise ValueError('Invalid agreement cutoff')
    if args.action=='auth' and not (1<=args.bits<=4096 and 0<=args.max_errors<args.bits):
        raise ValueError('Invalid response length or threshold')
    db=database(args.db); link=None
    try:
        if args.action=='export': export(db,args.directory); return
        link=HardwareLink(args.port)
        if args.action=='ping': print(link.command('PING'))
        elif args.action=='loop': print(link.command('LOOP '+args.challenge))
        elif args.action=='probe':
            bits=read_bits(link,args.challenge,args.repeats)
            print(json.dumps(dict(challenge=args.challenge,raw_bits=bits,majority=int(bits.count('1')>args.repeats//2)),indent=2))
        elif args.action=='enroll': enroll(db,link,args)
        elif args.action=='auth': authenticate(db,link,args)
        elif args.action=='characterize': characterize(db,link,args)
    finally:
        if link is not None: link.close()
        db.close()

if __name__=='__main__':
    try: main()
    except (Exception,KeyboardInterrupt) as error: raise SystemExit('ERROR: '+str(error))
