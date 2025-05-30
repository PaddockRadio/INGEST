import re

def sanitize_filename(name):
    name = re.sub(r'[\/*?:"<>|]', "_", name)
    name = re.sub(r'\s+', '_', name)
    return name.strip('_')

def clean_text(text):
    lines = text.splitlines()
    clean = []
    skip_patterns = ['Forwarded message', 'From:', 'Date:', 'Subject:', 'To:']
    for line in lines:
        if not any(line.startswith(p) for p in skip_patterns):
            clean.append(line)
    return '\n'.join(clean)
