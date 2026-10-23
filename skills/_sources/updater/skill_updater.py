"""Review-first updater for Claude skills. Check never executes upstream code."""
from __future__ import annotations
import argparse, concurrent.futures, datetime as dt, hashlib, json, os, posixpath, re, shutil, subprocess, sys, urllib.request, urllib.error, time, zipfile
from pathlib import Path, PurePosixPath

EXCLUDED = {'node_modules', '.git', '__pycache__', '.venv'}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def read_json(path, default=None):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else default

def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    temp.replace(path)

def contained(root, relative):
    parts=PurePosixPath(relative).parts
    if not parts or PurePosixPath(relative).is_absolute() or any(x in ('..','') or ':' in x for x in parts):
        raise ValueError(f'Invalid relative path: {relative}')
    result=(root/Path(*parts)).resolve()
    if not result.is_relative_to(root.resolve()) or result==root.resolve():
        raise ValueError(f'Path outside root: {relative}')
    return result

def request(url, binary=False):
    req=urllib.request.Request(url,headers={'User-Agent':'Claude-Skills-Review-Updater','Accept':'application/vnd.github+json'})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req,timeout=90) as response:
                data=response.read(110*1024*1024)
            break
        except urllib.error.HTTPError as error:
            if error.code not in (429,502,503) or attempt==3: raise
            retry=error.headers.get('Retry-After','')
            delay=min(int(retry),20) if retry.isdigit() else (2+attempt*3)
            time.sleep(delay)
    if len(data)>=110*1024*1024: raise ValueError('Source file exceeds 110 MiB')
    return data if binary else json.loads(data)

def git_blob(data):
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()

def normalize(data):
    return data.replace(b'\r\n',b'\n')

def patch_bytes(repo, remote, data, commit):
    if remote.endswith('skills/_jutsu/ui-ux-pro-max/SKILL.md'):
        data=re.sub(rb'(?m)^name: ui-ux-pro-max\r?$',b'name: genjutsu-ui-ux-pro-max',data)
    if repo=='morluto/rea' and remote.endswith('.md'):
        def external_link(match):
            relative=match.group(1).decode()
            resolved=posixpath.normpath(posixpath.join(posixpath.dirname(remote),relative))
            if resolved.startswith('../'): raise ValueError('External documentation path escapes upstream repository')
            return b'](https://github.com/morluto/rea/blob/'+commit.encode()+b'/'+resolved.encode()+b')'
        data=re.sub(rb'\]\(((?:\.\./){3,}[^\s)]+)\)',external_link,data)
    if repo=='zanwei/design-dna' and remote=='scripts/package.json':
        obj=json.loads(data)
        obj.setdefault('dependencies',{})['sharp']='0.35.5'
        # Preserve portable declaration required by sharp 0.35.x.
        obj.setdefault('engines',{})['node']='>=20.9.0'
        data=(json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode()
    return data

def same_content(relative, first, second):
    if relative.endswith('package.json'):
        try: return json.loads(first)==json.loads(second)
        except (ValueError,UnicodeError): pass
    return normalize(first)==normalize(second)

def validate_data(data):
    if re.search(rb'(?:sk-ant-api\d\d-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)',data):
        raise ValueError('Possible credential detected in candidate; review manually')

def snapshot(source, cache):
    """Fetch public Git metadata without consuming the anonymous GitHub REST quota."""
    repo=source['repo']; ref=source.get('ref','main')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9/_.-]*',ref):
        raise ValueError('Invalid configured repository or ref')
    directory=contained(cache,repo)
    directory.parent.mkdir(parents=True,exist_ok=True)
    def git(*args):
        result=subprocess.run(['git',*args],check=True,capture_output=True,timeout=180)
        return result.stdout
    if not directory.exists():
        git('clone','--bare','--filter=blob:none','--depth','1','--single-branch','--branch',ref,f'https://github.com/{repo}.git',str(directory))
        commit=git('-C',str(directory),'rev-parse','HEAD').decode().strip()
    else:
        git('-C',str(directory),'fetch','--depth','1','--filter=blob:none','origin',ref)
        commit=git('-C',str(directory),'rev-parse','FETCH_HEAD').decode().strip()
    entries=[]
    for line in git('-C',str(directory),'ls-tree','-r','-z','--full-tree',commit).split(b'\0'):
        if not line: continue
        header,path=line.split(b'\t',1); mode,kind,sha=header.decode().split(' ')
        entries.append({'path':path.decode('utf-8'),'mode':mode,'type':kind,'sha':sha})
    return commit,{'tree':entries,'truncated':False}

def source_plan(source, local, stage, previous_owned):
    repo=source['repo']
    commit,tree=snapshot(source,stage.parents[2]/'git-cache')
    if tree.get('truncated'): raise ValueError(f'{repo}: truncated tree')
    changes=[]; owned=[]
    for mapping in source['mappings']:
        prefix=mapping['path'].strip('/')
        required=(prefix+'/' if prefix else '')+'SKILL.md'
        if mapping['name']!='_jutsu' and not any(e['path']==required and e['type']=='blob' for e in tree['tree']):
            raise ValueError(f'Upstream skill missing or moved: {repo}/{required}; no automatic removals')
        if mapping['name']=='_jutsu' and not any(e['path'].startswith(prefix+'/') and e['path'].endswith('/SKILL.md') for e in tree['tree']):
            raise ValueError(f'Internal modules missing or moved: {repo}/{prefix}')
        for entry in tree['tree']:
            remote=entry['path']
            if prefix:
                if not remote.startswith(prefix+'/'): continue
                suffix=remote[len(prefix)+1:]
            else:
                suffix=remote
                if suffix not in ('SKILL.md','LICENSE') and not suffix.startswith(('scripts/','references/')): continue
            if entry['type']!='blob' or any(p in EXCLUDED for p in PurePosixPath(suffix).parts): continue
            if entry.get('mode')=='120000': raise ValueError(f'Symlink rejected: {repo}/{remote}')
            relative=mapping['name']+'/'+suffix
            target=contained(local,relative)
            owned.append(relative)
            before=target.read_bytes() if target.is_file() else None
            if before is not None and (git_blob(before)==entry['sha'] or git_blob(normalize(before))==entry['sha']): continue
            data=request(f'https://raw.githubusercontent.com/{repo}/{commit}/{remote}',True)
            if data.startswith(b'version https://git-lfs.github.com/spec/v1'):
                data=request(f'https://media.githubusercontent.com/media/{repo}/{commit}/{remote}',True)
                if data.startswith(b'version https://git-lfs.github.com/spec/v1'): raise ValueError('Unresolved LFS pointer')
            data=patch_bytes(repo,remote,data,commit)
            if before is not None and same_content(relative,before,data): continue
            validate_data(data)
            candidate=contained(stage,relative)
            candidate.parent.mkdir(parents=True,exist_ok=True); candidate.write_bytes(data)
            changes.append({'path':relative,'kind':'modify' if before is not None else 'add','before_sha256':digest(before) if before is not None else None,'after_sha256':digest(data)})
    # Only previously tracked upstream files can be removed. Local additions survive.
    for relative in sorted(set(previous_owned or [])-set(owned)):
        target=contained(local,relative)
        if target.is_file(): changes.append({'path':relative,'kind':'remove','before_sha256':digest(target.read_bytes()),'after_sha256':None})
    return {'repo':repo,'commit':commit,'changes':changes,'owned':sorted(set(owned))}

def check(config, home):
    local=Path(config['skills']); state=read_json(home/'state.json',{})
    stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    folder=home/'reports'/stamp; stage=folder/'candidate'; stage.mkdir(parents=True)
    sources=[]; errors=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        jobs={pool.submit(source_plan,s,local,stage,state.get('owned',{}).get(s['repo'])):s['repo'] for s in config['sources']}
        for future in concurrent.futures.as_completed(jobs):
            try: sources.append(future.result())
            except Exception as error: errors.append({'repo':jobs[future],'error':str(error)})
    changes=sorted([c for s in sources for c in s['changes']],key=lambda c:c['path'])
    # Reviewable diff is data only; no newly downloaded code runs during checks.
    import difflib
    with (folder/'changes.diff').open('w',encoding='utf-8',newline='\n') as diff:
        for change in changes:
            old=contained(local,change['path']); new=contained(stage,change['path'])
            try:
                first=old.read_text(encoding='utf-8').splitlines(True) if old.is_file() else []
                second=new.read_text(encoding='utf-8').splitlines(True) if new.is_file() else []
                diff.writelines(difflib.unified_diff(first,second,fromfile='installed/'+change['path'],tofile='candidate/'+change['path']))
            except UnicodeError: diff.write(f'Binary file changed: {change["path"]}\n')
    fingerprint=digest(json.dumps({'changes':changes,'errors':errors},sort_keys=True).encode())
    report={'created_utc':stamp,'local_root':str(local.resolve()),'repository':config['repository'],'sources':sorted(sources,key=lambda s:s['repo']),'changes':changes,'errors':errors,'fingerprint':fingerprint,'status':'failed' if errors else ('review_required' if changes else 'up_to_date'),'cowork_uploaded':False}
    write_json(folder/'report.json',report)
    approval=digest((folder/'report.json').read_bytes())
    lines=['# Claude skills 更新檢查','',f'狀態：{report["status"]}',f'檢查來源：{len(sources)}/{len(config["sources"])}',f'待審查檔案：{len(changes)}','','本次僅準備候選檔案，未修改已安裝技能、未執行下載的腳本。','',f'核准碼：`{approval}`','','## 變更','']
    lines += [f'- {c["kind"]}: `{c["path"]}`' for c in changes] or ['- 無變更']
    lines += ['','## 錯誤','']+[f'- {e["repo"]}: {e["error"]}' for e in errors]
    (folder/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    latest={'report':str(folder/'report.json'),'approval':approval,'fingerprint':fingerprint,'status':report['status'],'changed_files':len(changes),'errors':errors,'notify':fingerprint!=state.get('fingerprint') and bool(changes or errors)}
    write_json(home/'latest.json',latest)
    state['fingerprint']=fingerprint
    state.setdefault('owned',{})
    for source in sources: state['owned'].setdefault(source['repo'],source['owned'])
    write_json(home/'state.json',state)
    print(json.dumps(latest,ensure_ascii=False))
    return 1 if errors else 0

def backup_files(rooted_files, output):
    metadata=[]
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for index,(root,relative) in enumerate(rooted_files):
            file=contained(root,relative); record={'root':str(root.resolve()),'path':relative,'exists':file.is_file(),'entry':f'files/{index}'}
            if file.is_file(): archive.writestr(record['entry'],file.read_bytes())
            metadata.append(record)
        archive.writestr('backup.json',json.dumps(metadata,ensure_ascii=False))
    return metadata

def restore_backup(archive_path, allowed_roots):
    allowed={str(p.resolve()) for p in allowed_roots}
    with zipfile.ZipFile(archive_path) as archive:
        records=json.loads(archive.read('backup.json'))
        for row in records:
            root=Path(row['root'])
            if str(root.resolve()) not in allowed: raise ValueError('Backup root not allowed')
            file=contained(root,row['path'])
            if row['exists']:
                file.parent.mkdir(parents=True,exist_ok=True); file.write_bytes(archive.read(row['entry']))
            elif file.is_file(): file.unlink()

def run(command, cwd):
    return subprocess.run(command,cwd=cwd,check=True,text=True,capture_output=True).stdout

def apply(config, home, report_path, approval, publish=False):
    if digest(report_path.read_bytes())!=approval: raise ValueError('Approval does not match the exact report')
    report=read_json(report_path)
    if report['errors'] or not report['changes']: raise ValueError('Cannot apply incomplete or empty report')
    local=Path(config['skills']).resolve(); repo=Path(config['repository']).resolve(); repo_skills=repo/'skills'
    if report['local_root']!=str(local): raise ValueError('Installed root mismatch')
    if run(['git','status','--porcelain'],repo).strip(): raise ValueError('Repository has uncommitted changes; preserve and resolve them first')
    run(['git','pull','--ff-only'],repo)
    affected=[c['path'] for c in report['changes']]
    for change in report['changes']:
        path=contained(local,change['path']); before=digest(path.read_bytes()) if path.is_file() else None
        if before!=change['before_sha256']: raise ValueError(f'Installed file changed since review: {change["path"]}')
        if change['kind']!='remove' and digest(contained(report_path.parent/'candidate',change['path']).read_bytes())!=change['after_sha256']: raise ValueError('Candidate was modified after review')
        repository_file=contained(repo_skills,change['path'])
        if repository_file.is_file() and path.is_file() and not same_content(change['path'],repository_file.read_bytes(),path.read_bytes()): raise ValueError(f'Repository and local skill differ: {change["path"]}')
    extras=['_sources/shared-skills-manifest.json','design-dna/scripts/package-lock.json']
    files=[(root,path) for root in (local,repo_skills) for path in sorted(set(affected+extras))]
    stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backups=home/'backups'; backups.mkdir(parents=True,exist_ok=True); backup=backups/(stamp+'.zip')
    backup_files(files,backup)
    log={'report':str(report_path),'backup':str(backup),'status':'applying'}
    write_json(home/'last-apply.json',log)
    try:
        for change in report['changes']:
            for root in (local,repo_skills):
                target=contained(root,change['path'])
                if change['kind']=='remove':
                    if target.is_file(): target.unlink()
                else:
                    target.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copy2(contained(report_path.parent/'candidate',change['path']),target)
        if any(p.startswith('design-dna/scripts/') for p in affected):
            # Explicit apply approval covers these reviewed scripts; check never runs them.
            run([config['npm'],'install','--ignore-scripts'],local/'design-dna/scripts')
            run([config['npm'],'test'],local/'design-dna/scripts')
            run([config['npm'],'audit','--audit-level=moderate'],local/'design-dna/scripts')
            shutil.copy2(local/'design-dna/scripts/package-lock.json',repo_skills/'design-dna/scripts/package-lock.json')
        names=[]
        for file in local.rglob('SKILL.md'):
            if any(part in EXCLUDED for part in file.relative_to(local).parts): continue
            match=re.search(r'^name:\s*[\"\']?([^\r\n\"\']+)',file.read_text(encoding='utf-8-sig'),re.M)
            if not match: raise ValueError(f'Missing skill name: {file}')
            names.append(match.group(1))
        if len(names)!=len(set(names)): raise ValueError('Duplicate skill names after update')
        manifest=read_json(repo_skills/'_sources/shared-skills-manifest.json')
        version=manifest['plugin']['version'].split('.')
        version[-1]=str(int(version[-1])+1); manifest['plugin']['version']='.'.join(version)
        manifest['account_installation_verified']=False
        manifest['cowork_update_pending']=True
        for root in (local,repo_skills): write_json(root/'_sources/shared-skills-manifest.json',manifest)
        artifacts=home/'artifacts'; artifacts.mkdir(exist_ok=True)
        plugin=artifacts/f'austen-shared-skills-{manifest["plugin"]["version"]}.zip'
        run([sys.executable,str(repo_skills/'_sources/build_shared_plugin.py'),'--output',str(plugin)],repo)
        log.update(status='applied_cowork_upload_pending',plugin=str(plugin))
    except Exception as error:
        restore_backup(backup,[local,repo_skills])
        # Restore dependency installation to the backed-up lockfile if needed.
        if any(p.startswith('design-dna/scripts/') for p in affected):
            try: run([config['npm'],'ci','--ignore-scripts'],local/'design-dna/scripts')
            except Exception as recovery: log['dependency_recovery_error']=str(recovery)
        log.update(status='rolled_back',error=str(error)); write_json(home/'last-apply.json',log)
        raise
    state=read_json(home/'state.json',{}); state.setdefault('owned',{})
    for source in report['sources']: state['owned'][source['repo']]=source['owned']
    write_json(home/'state.json',state)
    if publish:
        try:
            relative_paths=['skills/'+p for p in sorted(set(affected+extras))]
            run(['git','add','--',*relative_paths],repo)
            run(['git','commit','-m','Apply reviewed Claude skill updates'],repo)
            run(['git','push','origin','main'],repo)
            log['github_pushed']=True
        except Exception as error:
            log.update(status='applied_github_push_pending',github_pushed=False,error=str(error))
            write_json(home/'last-apply.json',log); raise
    write_json(home/'last-apply.json',log)
    print(json.dumps(log,ensure_ascii=False))
    return 0

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['check','apply','rollback'])
    parser.add_argument('--config',type=Path,default=Path(__file__).with_name('config.json'))
    parser.add_argument('--report',type=Path); parser.add_argument('--approve'); parser.add_argument('--publish',action='store_true'); parser.add_argument('--backup',type=Path)
    args=parser.parse_args(); config=read_json(args.config); home=args.config.resolve().parent
    try:
        if args.action=='check': return check(config,home)
        if args.action=='apply':
            if not args.report or not args.approve: parser.error('apply requires --report and --approve SHA256')
            return apply(config,home,args.report.resolve(),args.approve,args.publish)
        if not args.backup: parser.error('rollback requires --backup')
        if not args.backup.resolve().is_relative_to((home/'backups').resolve()): raise ValueError('Backup must be in configured backups directory')
        restore_backup(args.backup,[Path(config['skills']),Path(config['repository'])/'skills'])
        print('Restored local/repository files. Git history and Cowork account were not changed. Reinstall dependencies from lockfile if needed.')
        return 0
    except Exception as error:
        print(f'ERROR: {error}',file=sys.stderr); return 1

if __name__=='__main__': sys.exit(main())
