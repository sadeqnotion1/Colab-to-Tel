# How to Use Streaming ZIP Extraction

## Quick Start (3 Steps)

### ✅ Step 1: Test That It Works (5 minutes)

Run the quick test to make sure everything is working:

```bash
python quick_test.py
```

**What it does:**
- Creates a small test ZIP
- Extracts it with streaming
- Tests selective extraction (CSV only)
- Shows you it all works!

**Expected output:**
```
🎉 All tests PASSED! Streaming extraction works perfectly!
```

---

### ✅ Step 2: Use With Your FINRA Data

#### Option A: Google Colab (Recommended)

1. **Open Google Colab:** https://colab.research.google.com
2. **Copy the script:** Open `extract_finra.py` and copy all the code
3. **Create new Colab notebook** and paste the code
4. **Update these 3 lines at the top:**
   ```python
   ZIP_PATH = "/content/drive/My Drive/finra/FINRA_archive.zip"  # Your ZIP location
   EXTRACT_TO = "/content/drive/My Drive/finra/extracted"        # Where to extract
   FILE_FILTER = ['.csv']                                         # What to extract
   ```
5. **Run the cell!**

#### Option B: Run Locally

1. **Update paths in `extract_finra.py`**
2. **Run:**
   ```bash
   cd Telegram-Leecher-Gemini/Telegram-Leecher-Gemini
   python extract_finra.py
   ```

---

### ✅ Step 3: Monitor Progress

The script will show progress like this:

```
[ 25.0%] File  250/1000 | ETA:   15.2m | Elapsed:   5.1m | data/2024/report_001.csv (2.3 MB)
[ 50.0%] File  500/1000 | ETA:   10.1m | Elapsed:  10.2m | data/2024/report_002.csv (1.8 MB)
[ 75.0%] File  750/1000 | ETA:    5.0m | Elapsed:  15.3m | data/2024/report_003.csv (2.1 MB)
[100.0%] File 1000/1000 | ETA:    0.0s | Elapsed:  20.4m | data/2024/report_004.csv (1.9 MB)

✅ EXTRACTION COMPLETE!
   Files extracted: 1000
   Total size: 6.50 GB
   Time: 20.4 minutes
```

---

## What Each File Does

### `quick_test.py` - Quick Test
- **Purpose:** Verify streaming extraction works
- **Runtime:** 5 seconds
- **Use when:** You want to test before using with real data

### `extract_finra.py` - FINRA Extraction
- **Purpose:** Extract your 65 GB FINRA archive
- **Runtime:** 30-60 minutes (depends on size and filter)
- **Use when:** Ready to extract your real data

### `test_streaming_extraction.ipynb` - Full Test Suite
- **Purpose:** Comprehensive testing in Google Colab
- **Runtime:** 10-15 minutes
- **Use when:** You want to test multiple scenarios

---

## Configuration Options

### File Filter (What to Extract)

```python
# Extract only CSV files (recommended for FINRA)
FILE_FILTER = ['.csv']

# Extract CSV and JSON files
FILE_FILTER = ['.csv', '.json']

# Extract everything (will take longer!)
FILE_FILTER = None
```

### Chunk Size (How Much Memory to Use)

```python
# Low memory (256 KB chunks)
CHUNK_SIZE = 256 * 1024

# Default (1 MB chunks) - recommended
CHUNK_SIZE = 1024 * 1024

# High speed (4 MB chunks) - use if you have lots of RAM
CHUNK_SIZE = 4 * 1024 * 1024
```

---

## Expected Performance

### Small Archives (< 1 GB)
- **Time:** 1-2 minutes
- **Memory:** ~2 MB
- **Status:** Very fast

### Medium Archives (1-10 GB)
- **Time:** 5-15 minutes
- **Memory:** ~2-4 MB
- **Status:** Good speed

### Large Archives (10-65 GB)
- **Time:** 30-90 minutes
- **Memory:** ~2-4 MB (constant!)
- **Status:** Stable, won't crash

### With Selective Filter (e.g., CSV only)
- **Time:** Much faster (only extracts matching files)
- **Example:** 65 GB archive with 10% CSVs = 6.5 GB = ~10 minutes

---

## Troubleshooting

### "ZIP file not found"
- **Fix:** Update `ZIP_PATH` to the correct location of your archive

### "Memory still running out"
- **Fix:** Reduce chunk size:
  ```python
  CHUNK_SIZE = 256 * 1024  # Use 256 KB instead of 1 MB
  ```

### "Too slow on Google Drive"
- **Fix:** Extract to `/tmp` first, then move:
  ```python
  EXTRACT_TO = "/tmp/extracted"  # Much faster!
  # Then move: shutil.move("/tmp/extracted", "/content/drive/My Drive/final")
  ```

### "No files match the filter"
- **Fix:** Check what extensions are in your ZIP:
  1. The script shows file types during Step 2
  2. Update `FILE_FILTER` to match available types

---

## Tips

### ✅ Best Practices

1. **Start with a filter** - Extract only what you need (e.g., CSVs)
2. **Inspect first** - The script shows contents before extracting
3. **Monitor progress** - Watch the ETA to know how long it will take
4. **Keep original** - Don't delete ZIP until you verify extraction

### ⚠️ Things to Know

1. **Progress updates every file** - For 1000 files, you'll see 1000 progress lines
2. **Time varies** - Google Drive is slower than local disk
3. **Can resume** - If Colab disconnects, extracted files stay on Drive
4. **Memory safe** - Won't crash even with huge archives

---

## Quick Reference

| Task | Command | Time |
|------|---------|------|
| **Quick test** | `python quick_test.py` | 5 seconds |
| **Extract FINRA data** | `python extract_finra.py` | 30-60 min |
| **Full test suite** | Open `test_streaming_extraction.ipynb` in Colab | 10-15 min |

---

## Need Help?

Check the detailed documentation:
- **Full guide:** `STREAMING_EXTRACTION.md`
- **Implementation details:** `IMPLEMENTATION_SUMMARY.md`

---

**You're all set!** Start with `quick_test.py` to verify it works, then use `extract_finra.py` for your real data. 🚀
