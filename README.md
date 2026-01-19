# trackid

CLI tool for identifying music tracks using Shazam and ACRCloud.

```
$ trackid identify "https://soundcloud.com/robot-heart/blondish-robot-heart-burning-man-2018" --time 1:29:10
Downloading 1:29:00 - 1:29:30 from https://soundcloud.com/robot-heart/blondish-robot-heart-burning-man-2018...
Downloaded: 469KB
Trying 1 chunk(s) with shazam, acrcloud...
Chunk 0: match found

Track identified:

  Title:   Beachball 2017 (Sebastien Remix)
  Artist:  Nalin & Kane
  Album:   Beachball 2017 (Sebastien Remix) - Single
  Service: shazam
  URL:     https://www.shazam.com/track/343597935/beachball-2017-sebastien-remix
```

## Installation

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/), ffmpeg, and yt-dlp.

```bash
# macOS
brew install ffmpeg yt-dlp

# Ubuntu/Debian
sudo apt install ffmpeg && pip install yt-dlp
```

```bash
git clone https://github.com/patforna/trackid
cd trackid
uv sync
```

Run with `uv run trackid ...` or activate the venv first.

### Docker

If you prefer containers:

```bash
docker build -t trackid .
docker run --rm trackid identify "https://soundcloud.com/robot-heart/blondish-robot-heart-burning-man-2018" -t 1:29:10
```

For local files, mount a volume: `docker run --rm -v $(pwd):/data trackid identify /data/song.mp3`

## Configuration

### ACRCloud (optional)

ACRCloud often identifies tracks that Shazam misses. To use it:

1. Create a free account at [ACRCloud](https://www.acrcloud.com/)
2. Create a project and get your credentials
3. Set environment variables (or create a `.env` file from `.env.example`):

```bash
export TRACKID_ACRCLOUD_HOST=identify-eu-west-1.acrcloud.com
export TRACKID_ACRCLOUD_ACCESS_KEY=your_access_key
export TRACKID_ACRCLOUD_ACCESS_SECRET=your_access_secret
```

If not configured, ACRCloud is skipped and only Shazam is used.

## Usage

### Identify a track

```bash
# From a local file
trackid identify song.mp3

# From a URL (requires --time)
trackid identify "https://soundcloud.com/robot-heart/blondish-robot-heart-burning-man-2018" --time 1:29:10
# -> Nalin & Kane - Beachball 2017 (Sebastien Remix)
```

### Multiple chunks

When identification fails, try more chunks. Each chunk extends the search window:

| Chunks | Duration | Coverage |
|--------|----------|----------|
| 1 | 30s | -10s to +20s from timestamp |
| 2 | 50s | -10s to +40s |
| 3 | 70s | -10s to +60s |
| 4 | 90s | -10s to +80s |
| 5 | 110s | -10s to +100s |

```bash
# Try 3 chunks (70 seconds of audio)
trackid identify "https://soundcloud.com/robot-heart/blondish-robot-heart-burning-man-2018" -t 1:29:10 -c 3
```

The first match found is returned. This handles DJ mix transitions where chunks might span track boundaries.

### Output formats

```bash
# Default: formatted table (stdout)
trackid identify "https://soundcloud.com/robot-heart/blondish-robot-heart-burning-man-2018" -t 1:29:10

# JSON (for scripting)
trackid identify "https://soundcloud.com/robot-heart/blondish-robot-heart-burning-man-2018" -t 1:29:10 --output json

# Plain text (artist - title)
trackid identify "https://soundcloud.com/robot-heart/blondish-robot-heart-burning-man-2018" -t 1:29:10 --output plain
# -> Nalin & Kane - Beachball 2017 (Sebastien Remix)
```

Status messages go to stderr, results to stdout. This allows piping:

```bash
trackid identify "https://soundcloud.com/robot-heart/blondish-robot-heart-burning-man-2018" -t 1:29:10 -o plain 2>/dev/null | pbcopy
```

### Download audio

```bash
# Download full track
trackid download "https://soundcloud.com/robot-heart/blondish-robot-heart-burning-man-2018" -o mix.mp3

# Download specific section
trackid download "https://soundcloud.com/robot-heart/blondish-robot-heart-burning-man-2018" -s 1:29:00 -e 1:32:00 -o clip.mp3
```

### Keep downloaded files

By default, temporary audio files are cleaned up. To keep them:

```bash
trackid identify "https://soundcloud.com/robot-heart/blondish-robot-heart-burning-man-2018" -t 1:29:10 --keep-files
# Files saved to ./data/ (or TRACKID_DATA_DIR)

trackid identify "https://soundcloud.com/robot-heart/blondish-robot-heart-burning-man-2018" -t 1:29:10 --output-dir ./my-clips
```

## Development

```bash
uv sync --all-extras
uv run pytest
```

## How it works

1. **Download**: Uses `yt-dlp` to download audio from URLs
2. **Process**: Uses `ffmpeg` to extract segments
3. **Identify**: Tries Shazam first, then ACRCloud (if configured). Returns the first match found.
4. **Report**: Outputs results to stdout

## Troubleshooting

### "No match found"

- The track might not be in the databases (unreleased, remix, obscure)
- Try a different timestamp with `--time`
- Try more chunks with `--chunks 3` or `--chunks 5`

### "Download failed"

- Check the URL is accessible
- Some private/geo-blocked content can't be downloaded
- Try updating yt-dlp: `pip install -U yt-dlp`
