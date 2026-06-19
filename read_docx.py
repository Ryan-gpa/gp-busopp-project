import zipfile, re, sys
path = sys.argv[1]
with zipfile.ZipFile(path) as z:
    with z.open('word/document.xml') as f:
        xml = f.read().decode('utf-8')
# preserve paragraph and table-cell boundaries as newlines
xml = re.sub(r'</w:p>', '\n', xml)
xml = re.sub(r'</w:tc>', ' \t', xml)
xml = re.sub(r'</w:tr>', '\n', xml)
text = re.sub(r'<[^>]+>', '', xml)
text = text.replace('\r','')
# collapse spaces but keep newlines/tabs
lines = []
for ln in text.split('\n'):
    ln = re.sub(r'[ ]+', ' ', ln).strip()
    if ln:
        lines.append(ln)
print('\n'.join(lines))
