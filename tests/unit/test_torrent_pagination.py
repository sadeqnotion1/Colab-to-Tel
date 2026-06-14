import pytest

def test_page_calculation():
    PAGE_SIZE = 10
    
    # 0 files
    total_count = 0
    total_pages = max(1, (total_count + PAGE_SIZE - 1) // PAGE_SIZE)
    assert total_pages == 1
    
    # 1 file
    total_count = 1
    total_pages = max(1, (total_count + PAGE_SIZE - 1) // PAGE_SIZE)
    assert total_pages == 1

    # 10 files
    total_count = 10
    total_pages = max(1, (total_count + PAGE_SIZE - 1) // PAGE_SIZE)
    assert total_pages == 1

    # 11 files
    total_count = 11
    total_pages = max(1, (total_count + PAGE_SIZE - 1) // PAGE_SIZE)
    assert total_pages == 2

    # 120 files
    total_count = 120
    total_pages = max(1, (total_count + PAGE_SIZE - 1) // PAGE_SIZE)
    assert total_pages == 12

def test_page_clamping():
    # Clamp helper: page = max(0, min(page, total_pages - 1))
    
    # page index out of bounds (too high)
    total_pages = 5
    page = 10
    page = max(0, min(page, total_pages - 1))
    assert page == 4
    
    # page index negative
    page = -3
    page = max(0, min(page, total_pages - 1))
    assert page == 0
    
    # page index valid
    page = 2
    page = max(0, min(page, total_pages - 1))
    assert page == 2

def test_file_slicing():
    files = [{'idx': i, 'path': f'file_{i}.txt'} for i in range(120)]
    PAGE_SIZE = 10
    
    # Page 0
    page = 0
    start = page * PAGE_SIZE
    end = min(start + PAGE_SIZE, len(files))
    page_files = files[start:end]
    assert len(page_files) == 10
    assert page_files[0]['idx'] == 0
    assert page_files[-1]['idx'] == 9

    # Page 11 (last page)
    page = 11
    start = page * PAGE_SIZE
    end = min(start + PAGE_SIZE, len(files))
    page_files = files[start:end]
    assert len(page_files) == 10
    assert page_files[0]['idx'] == 110
    assert page_files[-1]['idx'] == 119
