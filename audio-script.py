import os
import shutil
import subprocess
import argparse
from typing import List, Tuple
from tqdm import tqdm  # Provides rich progress bars
import datetime
import json
from pathlib import Path
import sys

# Define supported audio file extensions
AUDIO_EXTENSIONS = ['.flac', '.wav', '.m4a', '.mp3', '.ogg', '.opus', '.ape', '.wv', '.wma']

def directory_path(path: str) -> str:
    """Validates a directory path for argparse."""
    if os.path.isdir(path):
        return path
    raise argparse.ArgumentTypeError(f"'{path}' is not a directory")

def path_type(path: str) -> str:
    """Validates an existing path for argparse."""
    if os.path.exists(path):
        return path
    raise argparse.ArgumentTypeError(f"'{path}' does not exist")

def get_audio_files(directory: str) -> List[str]:
    """Finds audio files recursively in a directory."""
    audio_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if os.path.splitext(file)[1].lower() in AUDIO_EXTENSIONS:
                audio_files.append(os.path.join(root, file))
    return audio_files

def check_file_integrity(file_path: str) -> Tuple[str, str]:
    """Checks audio file integrity with FFmpeg."""
    try:
        result = subprocess.run(
            ['ffmpeg', '-v', 'error', '-i', file_path, '-f', 'null', '-'],
            capture_output=True, text=True
        )
        return ("PASSED", "") if not result.stderr else ("FAILED", result.stderr.strip())
    except Exception as e:
        return ("FAILED", str(e))

def check_integrity(path: str, verbose: bool = False, save_log: bool = True):
    """Verifies audio file integrity."""
    if not shutil.which('ffmpeg'):
        print("Error: FFmpeg is not installed or not in your PATH.")
        return

    if os.path.isfile(path) and os.path.splitext(path)[1].lower() in AUDIO_EXTENSIONS:
        audio_files = [path]
    elif os.path.isdir(path):
        audio_files = get_audio_files(path)
        if not audio_files:
            print(f"No audio files found in '{path}'.")
            return
    else:
        print(f"'{path}' is not a file or directory.")
        return

    log_file = None
    if save_log:  # Log by default unless explicitly disabled
        log_filename = f"integrity_check_log_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
        log_file = open(log_filename, 'w', encoding='utf-8')

    passed_count = 0
    failed_count = 0
    file_iterator = audio_files if verbose else tqdm(audio_files, desc="Checking files")

    for file_path in file_iterator:
        status, message = check_file_integrity(file_path)
        result_line = f"{status} {file_path}" + (f": {message}" if message else "")

        if verbose:
            print(result_line)
        if log_file:
            log_file.write(result_line + "\n")

        if status == "PASSED":
            passed_count += 1
        else:
            failed_count += 1

    summary = f"\nSummary:\nTotal files: {len(audio_files)}\nPassed: {passed_count}\nFailed: {failed_count}\n"
    if verbose:
        print(summary)
    if log_file:
        log_file.write(summary)
        log_file.close()
        print(f"Check complete. Log saved to '{log_filename}'")
    else:
        print("Check complete.")

def rename_cover_art(file_path: str, hide: bool):
    """Renames cover art files to hide or show."""
    file_name = os.path.basename(file_path)
    directory = os.path.dirname(file_path)

    if hide and file_name in ["cover.jpg", "cover.jpeg", "cover.png"]:
        new_name = os.path.join(directory, "." + file_name)
        if not os.path.exists(new_name):
            os.rename(file_path, new_name)
    elif not hide and file_name in [".cover.jpg", ".cover.jpeg", ".cover.png"]:
        new_name = os.path.join(directory, file_name[1:])
        if not os.path.exists(new_name):
            os.rename(file_path, new_name)

def process_cover_art(path: str, hide: bool):
    """Processes cover art files with progress."""
    total_files = sum(len(files) for _, _, files in os.walk(path))
    if total_files == 0:
        print(f"No files found in '{path}' to process.")
        return

    with tqdm(total=total_files, desc="Processing cover art") as progress:
        for root, _, files in os.walk(path):
            for file in files:
                rename_cover_art(os.path.join(root, file), hide)
                progress.update(1)

def analyze_audio(path: str, output_stream, show_progress: bool = True):
    """Analyzes audio metadata."""
    if not shutil.which('ffprobe'):
        print("Error: ffprobe is not installed or not in your PATH.")
        return

    if os.path.isfile(path):
        if os.path.splitext(path)[1].lower() in AUDIO_EXTENSIONS:
            audio_files = [Path(path)]
        else:
            print(f"'{path}' is not a supported audio file.")
            return
    elif os.path.isdir(path):
        audio_files = [file for ext in AUDIO_EXTENSIONS for file in Path(path).rglob(f"*{ext}")]
        if not audio_files:
            print(f"No audio files found in '{path}'.")
            return
    else:
        print(f"'{path}' is not a file or directory.")
        return

    file_iterator = tqdm(audio_files, desc="Analyzing audio") if show_progress else audio_files

    for audio_file in file_iterator:
        output_stream.write(f"Analyzing: {audio_file}\n")
        try:
            cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(audio_file)]
            result = subprocess.check_output(cmd, universal_newlines=True)
            data = json.loads(result)
            stream = data["streams"][0]

            codec = stream.get("codec_name", "N/A")
            sample_rate = stream.get("sample_rate", "N/A")
            channels = stream.get("channels", "N/A")
            bit_depth = stream.get("bits_per_raw_sample", "N/A")
            bit_rate = data["format"].get("bit_rate", "N/A")

            channel_info = "Mono" if channels == 1 else "Stereo" if channels == 2 else f"{channels} channels" if channels != "N/A" else "N/A"

            output_stream.write(f"  Bitrate: {bit_rate} bps\n" if bit_rate != "N/A" else "  Bitrate: N/A\n")
            output_stream.write(f"  Sample Rate: {sample_rate} Hz\n" if sample_rate != "N/A" else "  Sample Rate: N/A\n")
            output_stream.write(f"  Bit Depth: {bit_depth} bits\n" if bit_depth != "N/A" else "  Bit Depth: N/A\n")
            output_stream.write(f"  Channels: {channel_info}\n")
            output_stream.write(f"  Codec: {codec}\n")

            if audio_file.suffix.lower() == ".m4a":
                if "aac" in codec.lower():
                    output_stream.write("  [INFO] AAC (lossy) codec detected.\n")
                elif "alac" in codec.lower():
                    output_stream.write("  [INFO] ALAC (lossless) codec detected.\n")
                else:
                    output_stream.write(f"  [WARNING] Unknown codec: {codec}\n")
            elif audio_file.suffix.lower() in [".opus", ".mp3"]:
                output_stream.write(f"  [INFO] Lossy codec: {codec}\n")

            if bit_depth != "N/A" and int(bit_depth) < 16:
                output_stream.write("  [WARNING] Low bit depth may indicate lossy encoding.\n")
            if sample_rate != "N/A" and int(sample_rate) < 44100:
                output_stream.write("  [WARNING] Low sample rate may indicate lossy encoding.\n")

            output_stream.write("\n")
        except Exception as e:
            output_stream.write(f"  [ERROR] Failed to analyze: {e}\n")

def main():
    """Configures and runs subcommands."""
    parser = argparse.ArgumentParser(description="Tool for managing audio files")
    subparsers = parser.add_subparsers(dest="command", help="Available commands", required=True)

    check_parser = subparsers.add_parser("check", help="Verify audio file integrity")
    check_parser.add_argument("path", type=path_type, help="File or directory to check")
    check_parser.add_argument("--verbose", action="store_true", help="Print results to console (no progress bar)")
    check_parser.add_argument("--save-log", action="store_true", help="Save results to a log file")

    cover_parser = subparsers.add_parser("cover-art", help="Hide or show cover art files")
    cover_group = cover_parser.add_mutually_exclusive_group(required=True)
    cover_group.add_argument("--hide", action="store_true", help="Hide cover art by adding a dot prefix")
    cover_group.add_argument("--show", action="store_true", help="Show cover art by removing dot prefix")
    cover_parser.add_argument("path", type=directory_path, help="Directory to process")

    info_parser = subparsers.add_parser("info", help="Analyze audio file metadata")
    info_parser.add_argument("path", type=path_type, help="File or directory to analyze")
    info_parser.add_argument("-o", "--output", default="audio_analysis.txt", help="Output file for results")
    info_parser.add_argument("--verbose", action="store_true", help="Print results to console (no progress bar)")

    args = parser.parse_args()

    if args.command == "check":
        verbose = args.verbose
        save_log = args.save_log if verbose else True  # Log by default unless verbose overrides
        check_integrity(args.path, verbose=verbose, save_log=save_log)
    elif args.command == "cover-art":
        process_cover_art(args.path, args.hide)
    elif args.command == "info":
        if args.verbose:
            analyze_audio(args.path, sys.stdout, show_progress=False)
        else:
            output_file = f"audio_analysis_{datetime.datetime.now().strftime('%Y%m%d')}.txt" if args.output == "audio_analysis.txt" else args.output
            with open(output_file, "w") as f:
                analyze_audio(args.path, f)
            print(f"Analysis complete. Results saved to '{output_file}'")

if __name__ == "__main__":
    """Runs the script with Ctrl+C handling."""
    try:
        main()
    except KeyboardInterrupt:
        print("Quitting job...")
