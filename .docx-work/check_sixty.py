from pathlib import Path
import pdfplumber,json,hashlib
from PIL import Image,ImageOps,ImageDraw
root=Path('.docx-work/code-sixty');pdf=pdfplumber.open(next(root.glob('*.pdf'))).pages
assert len(pdf)==60,len(pdf)
for i,page in enumerate(pdf):
 lines=page.extract_text().splitlines()[1:]
 assert len(lines)==50,(i+1,len(lines))
 assert f'{i+1}/60' in page.extract_text(),i
manifest=json.loads(Path('.docx-work/source_manifest.json').read_text())
for f in manifest['files']:assert hashlib.sha256(Path(f['path']).read_bytes()).hexdigest()==f['sha256']
assert pdf[-1].extract_text().strip().endswith('return datetime.now(timezone.utc).isoformat()')
for batch in range(10):
 canvas=Image.new('RGB',(2100,1980),'#ddd')
 for j in range(6):
  n=batch*6+j+1
  im=Image.open(root/f'page-{n}.png');im.thumbnail((700,990))
  canvas.paste(im,((j%3)*700,(j//3)*990))
 canvas.save(root/f'contact-{batch+1}.jpg')
print('Verified: 60 pages, exactly 50 body lines each, 3000 total; pages 1–60; original source hashes unchanged; complete module ending.')
