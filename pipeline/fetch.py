"""Download every Dataverse input listed in pipeline/sources.json into build/downloads/dataverse/<key>/.

usage:
  python -I pipeline/fetch.py [KEY ...]     download (skips files already present with the right MD5)
  python -I pipeline/fetch.py --check       report datasets whose latest published version is newer than the pin

Some MIT datasets require a one-time "guestbook" response (name, email, institution, position) before
files can be downloaded. Provide it in the environment variable DATAVERSE_GUESTBOOK as JSON, or in a
git-ignored file `.dataverse-guestbook.json` at the repository root:
  {"name": "...", "email": "...", "institution": "...", "position": "..."}

Writes data/raw/dataverse_lock.csv (key, doi, version, file id, original file name, bytes, md5) so a build
can be traced to exact inputs. Uses only the standard library.
"""
import csv, hashlib, json, os, sys, urllib.parse, urllib.request

API = 'https://dataverse.harvard.edu/api'
OUT = 'build/downloads/dataverse'
LOCK = 'data/raw/dataverse_lock.csv'
UA = {'User-Agent': 'pollkadot-data-pipeline'}


def get_json(url, data=None):
    req = urllib.request.Request(url, data=data, headers={**UA, **({'Content-Type': 'application/json'} if data else {})})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def version_info(doi, version):
    q = urllib.parse.quote(doi, safe='')
    return get_json(f'{API}/datasets/:persistentId/versions/{version}?persistentId={q}')['data']


def guestbook():
    raw = os.environ.get('DATAVERSE_GUESTBOOK')
    if not raw and os.path.exists('.dataverse-guestbook.json'):
        raw = open('.dataverse-guestbook.json', encoding='utf-8').read()
    if not raw:
        sys.exit('This dataset needs a Dataverse guestbook response: set DATAVERSE_GUESTBOOK or create .dataverse-guestbook.json')
    return json.loads(raw)


def download_url(fid, needs_gb):
    if not needs_gb:
        return f'{API}/access/datafile/{fid}?format=original'
    body = json.dumps({'guestbookResponse': guestbook()}).encode()
    return get_json(f'{API}/access/datafile/{fid}?format=original', data=body)['data']['signedUrl']


def md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


def fetch(entry, lock):
    d = version_info(entry['doi'], entry['version'])
    needs_gb = d.get('guestbookId') is not None
    want = entry['files']
    files = [x['dataFile'] for x in d['files'] if want == '*' or x['dataFile']['filename'] in want]
    missing = [] if want == '*' else sorted(set(want) - {f['filename'] for f in files})
    if missing: sys.exit(f"{entry['key']}: not in version {entry['version']}: {missing}")
    os.makedirs(f"{OUT}/{entry['key']}", exist_ok=True)
    for f in files:
        name = f.get('originalFileName') or f['filename']
        path = f"{OUT}/{entry['key']}/{name}"
        expect = (f.get('checksum') or {}).get('value') or f.get('md5')
        if not (os.path.exists(path) and expect and md5(path) == expect):
            print(f"  {entry['key']}/{name} ({(f.get('originalFileSize') or f.get('filesize') or 0)/1e6:.0f} MB)", flush=True)
            tmp = path + '.part'
            with urllib.request.urlopen(urllib.request.Request(download_url(f['id'], needs_gb), headers=UA), timeout=600) as r, open(tmp, 'wb') as o:
                while b := r.read(1 << 20): o.write(b)
            os.replace(tmp, path)
            got = md5(path)
            if expect and got != expect: print(f'    WARNING md5 {got} != published {expect}')
        lock.append(dict(key=entry['key'], doi=entry['doi'], version=entry['version'], file_id=f['id'],
                         file=name, bytes=os.path.getsize(path), md5=md5(path)))


def main():
    cfg = json.load(open('pipeline/sources.json'))['dataverse']
    args = sys.argv[1:]
    if args[:1] == ['--check']:
        found = []
        for e in cfg:
            v = version_info(e['doi'], ':latest-published')
            latest = f"{v['versionNumber']}.{v['versionMinorNumber']}"
            if latest != e['version']: found.append(f"UPDATE AVAILABLE: {e['key']} ({e['doi']}) pinned {e['version']}, latest {latest}")
            print(f"{e['key']:20s} pinned {e['version']:6s} latest {latest}")
        # MIT election-returns datasets that aren't used yet (e.g. a new election year)
        known = {e['doi'] for e in cfg}
        q = f'{API}/search?q=*&type=dataset&subtree=medsl&per_page=100&sort=date&order=desc'
        for it in get_json(q)['data']['items']:
            name = it.get('name', '')
            if it['global_id'] not in known and ('Precinct-Level Returns' in name or 'County' in name) \
                    and any(str(y) in name for y in range(2026, 2040)):
                found.append(f"NEW DATASET: {name} ({it['global_id']}, published {it.get('published_at', '')[:10]})")
        print('\n'.join(found) if found else 'No updates.')
        if found and os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'], 'a') as f: f.write('found=true\n')
            with open('build/data_updates.md', 'w') as f:
                f.write('The weekly data check found newer source data:\n\n' + '\n'.join(f'- {x}' for x in found) +
                        '\n\nTo use it: bump the versions in `pipeline/sources.json` (or add the new dataset), then follow '
                        '"Rebuilding the data" in DEVELOPMENT.md.\n')
        return
    sel = [e for e in cfg if not args or e['key'] in args]
    old = [r for r in csv.DictReader(open(LOCK))] if os.path.exists(LOCK) else []
    lock = [r for r in old if r['key'] not in {e['key'] for e in sel}]
    for e in sel:
        print(e['key'], e['doi'], 'v' + e['version'], flush=True)
        fetch(e, lock)
    order = [e['key'] for e in cfg]
    lock.sort(key=lambda r: (order.index(r['key']) if r['key'] in order else 99, r['file']))
    with open(LOCK, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['key', 'doi', 'version', 'file_id', 'file', 'bytes', 'md5'])
        w.writeheader(); w.writerows(lock)
    print('wrote', LOCK, len(lock), 'files')


if __name__ == '__main__':
    main()
