from pathlib import Path
p=Path('.docx-work/build_documents.py')
s=p.read_text()
s=s.replace(" 'engine/modes.py', 'tools/adaptive_tools.py'", " 'engine/modes.py', 'engine/gaps.py', 'engine/bandit.py', 'tools/adaptive_tools.py'")
s=s.replace(' for p in cover:body.append(p)',' # User requests exactly sixty code pages, without a cover.\n if kind==\'code\':\n  for node in sect.findall(q(\'titlePg\')):sect.remove(node)\n  prop(sect,\'pgNumType\',start=1)\n else:\n  for p in cover:body.append(p)')
s=s.replace(' for page in pages:', ' for page_index,page in enumerate(pages):')
s=s.replace("   if i==0:prop(p.find(q('pPr')),'pageBreakBefore')", "   if i==0 and (kind!='code' or page_index>0):prop(p.find(q('pPr')),'pageBreakBefore')")
start=s.index('selected=rows\n')
s=s[:start]+'''assert len(rows)>3000
selected=rows[:1500]+rows[-1500:]
assert len(selected)==3000
codepages=[[paragraph(r[0],size=9,code=True) for r in selected[i:i+50]] for i in range(0,3000,50)]
assert len(codepages)==60 and all(len(page)==50 for page in codepages)
print(build('code',codepages))
Path('.docx-work/source_manifest.json').write_text(json.dumps({'files':manifest,'display_lines_total':len(rows),'excerpt':'First 1500 and last 1500 nonblank display lines of core modules in call-chain order; 60 pages of 50 lines, no cover','selected':selected},ensure_ascii=False,indent=2))
print(f'Core files: {len(files)}; available display lines: {len(rows)}; selected: {len(selected)}; pages: {len(codepages)}')
'''
p.write_text(s)
with Path('.docx-work/artifact.md').open('a') as f:f.write('\n最终修订：用户明确要求填满60页。增加engine/gaps.py与engine/bandit.py核心模块；按调用流程取前1500及后1500非空排版行，每页50行，共60页。取消封面，页码1–60；结尾保持persistence.py文件结尾。\n')
