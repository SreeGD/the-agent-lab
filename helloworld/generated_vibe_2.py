import os

def get_top_largest_files(root='.', top_n=5):
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip hidden directories
        dirnames[:] = [d for d in dirnames if not d.startswith('.')]
        for filename in filenames:
            if filename.startswith('.'):
                continue
            filepath = os.path.join(dirpath, filename)
            try:
                size = os.path.getsize(filepath)
                files.append((size, filepath))
            except OSError:
                continue
    files.sort(key=lambda x: x[0], reverse=True)
    return files[:top_n]

if __name__ == '__main__':
    top_files = get_top_largest_files('.')
    for size, path in top_files:
        print(f'{size} {path}')