import pdfplumber, sys

def dump(path, pages, exclude_rotated=True):
    with pdfplumber.open(path) as pdf:
        for pidx in pages:
            page = pdf.pages[pidx]
            words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
            # drop rotated "for personal use only" by upright filter via 'upright'
            rows = {}
            for w in words:
                if exclude_rotated and not w.get('upright', True):
                    continue
                y = round(w['top']/3)*3
                rows.setdefault(y, []).append((w['x0'], w['text']))
            print(f"\n===== PAGE {pidx+1} ({path}) =====")
            for y in sorted(rows):
                line = sorted(rows[y])
                print(" | ".join(t for _,t in line))

path = sys.argv[1]
pages = [int(p)-1 for p in sys.argv[2].split(',')]
dump(path, pages)
