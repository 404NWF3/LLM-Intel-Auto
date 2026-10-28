from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from lxml import etree as E
import shutil
p=Path('软著申请材料/大模型安全情报采集智能体软件_用户使用手册.docx')
shutil.copy2(p,'.docx-work/manual-user-revision-before.docx')
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
with ZipFile(p) as z:parts={n:z.read(n) for n in z.namelist()}
replacements={
'本文对应当前Python软件包版本V0.2.0。':'本手册适用于大模型安全情报采集智能体软件 V0.1.0。V0.1.0 为本系统的软件版本号，与 Python 运行环境版本无关；Python 版本要求见“本地部署与安装”章节。',
'准备完整项目目录，保留 backend、pyproject.toml、uv.lock 与 .env.example；所有命令均在项目根目录执行。':'项目根目录下，backend/ 存放后端代码，其中 backend/intel_agent/ 为情报采集核心，backend/console/ 为可视化控制台。pyproject.toml 定义项目依赖和启动入口，uv.lock 锁定依赖版本，.env.example 提供环境变量配置示例，复制为 .env 后填写实际配置。这些文件共同用于配置项目运行环境；本手册中的命令均在项目根目录执行。'}
counts={k:0 for k in replacements}
for n,b in list(parts.items()):
 if n=='word/document.xml' or n.startswith('word/header') and n.endswith('.xml'):
  r=E.fromstring(b)
  for para in r.findall('.//w:p',ns):
   ts=para.findall('.//w:t',ns)
   for old,new in list(replacements.items())+[('V0.2.0','V0.1.0')]:
    text=''.join(t.text or '' for t in ts)
    while old in text:
     start=text.index(old);end=start+len(old);offset=0
     for t in ts:
      v=t.text or '';a=offset;z=offset+len(v);offset=z
      if z<=start or a>=end:continue
      t.text=v[:max(0,start-a)]+(new if a<=start<z else '')+v[max(0,end-a):]
      t.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
     if old in counts:counts[old]+=1
     text=''.join(t.text or '' for t in ts)
  parts[n]=E.tostring(r,xml_declaration=True,encoding='UTF-8',standalone=True)
 elif n=='docProps/core.xml':parts[n]=b.replace(b'V0.2.0',b'V0.1.0')
assert all(v==1 for v in counts.values()),counts
with ZipFile(p,'w',ZIP_DEFLATED) as z:
 for n,b in parts.items():z.writestr(n,b)
print('Updated only requested text/version, preserved all other paragraph text and formatting.')
