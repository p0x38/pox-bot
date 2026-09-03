import gc
import os

from .cli import main

os.environ['MALLOC_TRIM_THRESHOLD_'] = '65536'
gc.set_threshold(400, 5, 5)

if __name__ == '__main__':
    main()
