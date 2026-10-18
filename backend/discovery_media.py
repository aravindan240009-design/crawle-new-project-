"""Optional local media extraction; no automatic model downloads or remote utilities."""
import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from .db import dump
from .discovery_store import emit
from .fetch import validate_url
from .models import now


def media_capabilities():
    tesseract = shutil.which('tesseract')
    languages = []
    if tesseract:
        try:
            result = subprocess.run([tesseract, '--list-langs'], capture_output=True, text=True, timeout=5,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            languages = [x.strip() for x in result.stdout.splitlines()[1:] if x.strip()]
        except (OSError, subprocess.TimeoutExpired):
            pass
    model = os.environ.get('RADAR_WHISPER_MODEL_DIR', '')
    asr = bool(model and Path(model).is_dir() and importlib.util.find_spec('faster_whisper'))
    return {'ocr': {'available': bool(tesseract and languages), 'languages': languages,
                    'reason': None if languages else 'Tesseract executable/language data unavailable; English eng and Tamil tam require local installation'},
            'asr': {'available': asr, 'reason': None if asr else 'Opt-in faster-whisper and RADAR_WHISPER_MODEL_DIR not configured; no model downloaded'},
            'ffmpeg': {'available': bool(shutil.which('ffmpeg'))},
            'direct_media': {'max_bytes': 2_000_000, 'manifests': False},
            'instagram': {'available': False, 'reason': 'No authorized Instagram professional-account API credentials configured; global reel search is not provided'}}


def register_media(db, cid, fid, item):
    try:
        validate_url(item['url'])
    except Exception as exc:
        emit(db, cid, 'media_rejected', item['url'], code=str(exc)[:200])
        return
    mid = hashlib.sha256((fid+item['url']).encode()).hexdigest()[:32]
    inserted = db.execute('INSERT OR IGNORE INTO media_jobs(id,campaign_id,frontier_id,url,status,created,updated,language) VALUES (?,?,?,?,?,?,?,?)',
                        (mid, cid, fid, item['url'], 'media_pending', now(), now(), item.get('language', 'unknown')))
    if inserted:
        emit(db, cid, 'media_queued', item['url'], {'kind': item['kind'], 'job_id': mid}, fid)


def local_extract(data, content_type, caps):
    if content_type in ('text/vtt', 'application/x-subrip'):
        text = data.decode('utf-8', errors='replace')
        # Keep timestamps beside text, stripping markup only.
        return re.sub(r'<[^>]{0,200}>', '', text)[:2000], 'captions', None
    with tempfile.TemporaryDirectory(prefix='radar-media-') as folder:
        path = Path(folder) / ('image.png' if content_type.startswith('image/') else 'clip.mp4')
        path.write_bytes(data)
        if content_type.startswith('image/'):
            if not caps['ocr']['available']:
                raise RuntimeError(caps['ocr']['reason'])
            from PIL import Image
            with Image.open(path) as img:
                if img.width*img.height > 20_000_000:
                    raise ValueError('Image pixel budget exceeded')
                img.load()
            languages = [x for x in ('eng', 'tam') if x in caps['ocr']['languages']]
            if not languages:
                raise RuntimeError('Neither English nor Tamil OCR language data is installed')
            result = subprocess.run([shutil.which('tesseract'), str(path), 'stdout', '-l', '+'.join(languages)], capture_output=True, timeout=30,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            if result.returncode:
                raise RuntimeError('Local OCR failed: ' + result.stderr.decode(errors='replace')[:200])
            return result.stdout.decode('utf-8', errors='replace')[:2000], 'ocr', '+'.join(languages)
        if content_type.startswith('video/') and caps['ocr']['available'] and caps['ffmpeg']['available']:
            # Sample at most six resized local frames. No manifest/remote protocol.
            pattern = Path(folder)/'frame-%02d.png'
            result = subprocess.run([shutil.which('ffmpeg'), '-nostdin', '-v', 'error', '-protocol_whitelist', 'file,pipe',
                '-f', 'mov', '-enable_drefs', '0', '-use_absolute_path', '0', '-i', str(path), '-t', '120', '-vf', 'fps=1/20,scale=960:-2', '-frames:v', '6', str(pattern)],
                capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            if result.returncode:
                raise RuntimeError('Local frame extraction failed; no remote fallback')
            languages = [x for x in ('eng', 'tam') if x in caps['ocr']['languages']]
            snippets = []
            for index, frame in enumerate(sorted(Path(folder).glob('frame-*.png'))[:6]):
                if not languages:
                    break
                ocr = subprocess.run([shutil.which('tesseract'), str(frame), 'stdout', '-l', '+'.join(languages)],
                    capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                if ocr.returncode == 0:
                    text = ocr.stdout.decode('utf-8', errors='replace').strip()
                    if text:
                        snippets.append(f'[sample around {index*20+10}s] {text[:280]}')
            if snippets:
                return '\n'.join(snippets)[:2000], 'frame_ocr', '+'.join(languages)
        if not caps['asr']['available']:
            raise RuntimeError(caps['asr']['reason'])
        if not caps['ffmpeg']['available']:
            raise RuntimeError('ffmpeg unavailable for bounded local audio extraction')
        wav = Path(folder)/'audio.wav'
        input_format = ['-f', 'mov', '-enable_drefs', '0', '-use_absolute_path', '0'] if content_type == 'video/mp4' else ['-f', 'mp3' if content_type == 'audio/mpeg' else 'wav']
        result = subprocess.run([shutil.which('ffmpeg'), '-nostdin', '-v', 'error', '-protocol_whitelist', 'file,pipe',
            *input_format, '-i', str(path), '-t', '120', '-vn', '-ac', '1', '-ar', '16000', str(wav)], capture_output=True, timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        if result.returncode:
            raise RuntimeError('Local media conversion failed; no remote fallback')
        from faster_whisper import WhisperModel
        model = WhisperModel(os.environ['RADAR_WHISPER_MODEL_DIR'], device='cpu', compute_type='int8', local_files_only=True, cpu_threads=2, num_workers=1)
        segments, info = model.transcribe(str(wav), beam_size=1)
        text = '\n'.join(f'[{s.start:.1f}-{s.end:.1f}] {s.text}' for s in segments)[:2000]
        return text, 'asr', info.language


def isolated_extract(data, content_type, caps):
    # A separate process bounds model load/inference time and memory lifetime.
    with tempfile.TemporaryDirectory(prefix='radar-extract-') as folder:
        path = Path(folder)/'input.bin'
        path.write_bytes(data)
        result = subprocess.run([sys.executable, '-m', 'backend.discovery_media', str(path), content_type, dump(caps)],
            capture_output=True, timeout=90, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        if result.returncode:
            raise RuntimeError(result.stderr.decode('utf-8', errors='replace')[-400:])
        return json.loads(result.stdout)


async def process_media(db, cid, fetcher, limit=3, gate=None, generation=1):
    caps = await asyncio.to_thread(media_capabilities)
    jobs = db.rows("SELECT * FROM media_jobs WHERE status='media_pending' ORDER BY created LIMIT ?", (limit,))
    for job in jobs:
        if gate:
            await gate()
        emit(db, cid, 'media_fetch_started', job['url'], task=job['frontier_id'])
        try:
            url, ct, data = await fetcher.blob(job['url'])
            emit(db, cid, 'media_extraction_started', url, {'content_type': ct, 'bytes': len(data)})
            text, method, language = await asyncio.to_thread(isolated_extract, data, ct, caps)
            evidence = [{'method': method, 'url': url, 'excerpt': text, 'retrieved': now(), 'content_hash': hashlib.sha256(data).hexdigest(),
                         'language': language, 'status': 'machine extraction; issuer and offer facts require review'}]
            db.execute("UPDATE media_jobs SET status='extracted',updated=?,evidence=?,language=?,error=NULL WHERE id=?", (now(), dump(evidence), language, job['id']))
            emit(db, cid, 'media_extraction_completed', url, {'job_id': job['id'], 'method': method, 'characters': len(text)})
        except Exception as exc:
            db.execute("UPDATE media_jobs SET status='unavailable',updated=?,error=? WHERE id=?", (now(), str(exc)[:400], job['id']))
            emit(db, cid, 'media_unavailable', job['url'], {'job_id': job['id']}, code=str(exc)[:400])
        if gate:
            await gate()
        rows = db.rows('SELECT v.data FROM live_membership m JOIN versions v ON v.id=m.version_id WHERE m.opportunity_id=?', (job['frontier_id'],))
        if rows:
            from .discovery_store import commit_live
            item = json.loads(rows[0]['data'])
            jobs_for_item = db.rows('SELECT status,evidence,error FROM media_jobs WHERE frontier_id=?', (job['frontier_id'],))
            item['media_status'] = 'extracted' if any(j['status'] == 'extracted' for j in jobs_for_item) else 'unavailable'
            item['media_limitations'] = [j['error'] for j in jobs_for_item if j['error']]
            for j in jobs_for_item:
                for e in json.loads(j['evidence']):
                    record = {k: e[k] for k in ('url', 'retrieved', 'content_hash')}
                    record.update(field='machine_' + e['method'], excerpt=e['excerpt'][:280])
                    if record not in item['evidence']:
                        item['evidence'].append(record)
            await asyncio.to_thread(commit_live, db, cid, generation, item)


if __name__ == '__main__':
    try:
        result = local_extract(Path(sys.argv[1]).read_bytes(), sys.argv[2], json.loads(sys.argv[3]))
        print(json.dumps(result, ensure_ascii=True))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
