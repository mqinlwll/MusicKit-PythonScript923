import os
import shutil
import subprocess
import argparse
from typing import List, Tuple
from tqdm import tqdm  # Third-party library for advanced progress bars
import datetime
import json
from pathlib import Path
import sys  # For sys.stdout in verbose mode

# Supported audio extensions
AUDIO_EXTENSIONS = ['.flac', '.wav', '.m4a', '.mp3', '.ogg', '.opus', '.ape', '.wv', '.wma']
# Global list of audio file extensions supported by the script

# Custom argument types
def directory_path(path):
    """Validate that a path is an existing directory.
    Args:
        path (str): Path to check.
    Returns:
        str: Path if it's a directory.
    Raises:
        argparse.ArgumentTypeError: If path is not a directory.
    """
    if os.path.isdir(path):
        return path
    raise argparse.ArgumentTypeError(f"{path} is not a directory")

def path_type(path):
    """Validate that a path exists (file or directory).
    Args:
        path (str): Path to check.
    Returns:
        str: Path if it exists.
    Raises:
        argparse.ArgumentTypeError: If path does not exist.
    """
    if os.path.exists(path):
        return path
    raise argparse.ArgumentTypeError(f"{path} does not exist")

# Check command helper functions
def get_audio_files(directory: str) -> List[str]:
    """Recursively find audio files in a directory with supported extensions.
    Args:
        directory (str): Directory to search.
    Returns:
        List[str]: List of audio file paths.
    Notes:
        - Uses os.walk for recursive traversal.
        - Matches against AUDIO_EXTENSIONS.
    """
    return [
        os.path.join(root, file)
        for root, _, files in os.walk(directory)
        for file in files
        if os.path.splitext(file)[1].lower() in AUDIO_EXTENSIONS
    ]

def check_file_integrity(file_path: str) -> Tuple[str, str]:
    """Use FFmpeg to verify audio file integrity.
    Args:
        file_path (str): Path to the audio file.
    Returns:
        Tuple[str, str]: (status, message) - 'PASSED' or 'FAILED', with error message if failed.
    Notes:
        - Runs FFmpeg with error-only output.
    """
    try:
        result = subprocess.run(
            ['ffmpeg', '-v', 'error', '-i', file_path, '-f', 'null', '-'],
            capture_output=True,
            text=True
        )
        return ("PASSED", "") if not result.stderr else ("FAILED", result.stderr.strip())
    except Exception as e:
        return "FAILED", str(e)

def check_integrity(path: str, verbose: bool = False, save_log: bool = True):
    """Check integrity of audio files with configurable output.
    Args:
        path (str): File or directory to check.
        verbose (bool): If True, print to console, no progress bar, log optional.
        save_log (bool): If True, save to log file; default True unless verbose overrides.
    Notes:
        - Supports single files or directories.
        - Log is saved by default unless verbose=True and save_log=False.
    """
    if not shutil.which('ffmpeg'):
        print("FFmpeg is not found. Please install FFmpeg and ensure it's in your PATH.")
        return

    # Determine audio files to process
    if os.path.isfile(path) and os.path.splitext(path)[1].lower() in AUDIO_EXTENSIONS:
        audio_files = [path]
    elif os.path.isdir(path):
        audio_files = get_audio_files(path)
        if not audio_files:
            print("No audio files found in the specified directory.")
            return
    else:
        print(f"{path} is neither a valid file nor directory.")
        return

    # Set up log file if saving is enabled
    log_file = None
    if save_log:
        log_filename = f"integrity_check_log_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
        log_file = open(log_filename, 'w', encoding='utf-8')

    passed_count = 0
    failed_count = 0

    # Choose iterator: tqdm for progress bar, plain list for verbose
    audio_files_iter = audio_files if verbose else tqdm(audio_files, desc="Checking files")

    for file_path in audio_files_iter:
        status, message = check_file_integrity(file_path)
        if status == "PASSED":
            if verbose:
                print(f"PASSED {file_path}")
            if save_log:
                log_file.write(f"PASSED {file_path}\n")
            passed_count += 1
        else:
            if verbose:
                print(f"FAILED {file_path}: {message}")
            if save_log:
                log_file.write(f"FAILED {file_path}: {message}\n")
            failed_count += 1

    # Generate and output summary
    summary = f"\nSummary:\nTotal files checked: {len(audio_files)}\nPassed: {passed_count}\nFailed: {failed_count}\n"
    if verbose:
        print(summary)
    if save_log:
        log_file.write(summary)
        log_file.close()
        print(f"Check completed. Log saved to {log_filename}")
    else:
        print("Check completed.")

# Cover-art functions
def rename_cover_art(file_path: str, hide: bool):
    """Rename cover art files to hide or show them.
    Args:
        file_path (str): Path to the file.
        hide (bool): True to hide (add dot), False to show (remove dot).
    """
    file_name = os.path.basename(file_path)
    dir_path = os.path.dirname(file_path)
    if hide and file_name in ["cover.jpg", "cover.jpeg", "cover.png"]:
        target_name = os.path.join(dir_path, "." + file_name)
        if not os.path.exists(target_name):
            os.rename(file_path, target_name)
    elif not hide and file_name in [".cover.jpg", ".cover.jpeg", ".cover.png"]:
        original_name = os.path.join(dir_path, file_name[1:])
        if not os.path.exists(original_name):
            os.rename(file_path, original_name)

def process_cover_art(path: str, hide: bool):
    """Process cover art files in a directory.
    Args:
        path (str): Directory to process.
        hide (bool): True to hide, False to show.
    Notes:
        - Uses tqdm for progress tracking.
    """
    total_files = sum(len(files) for _, _, files in os.walk(path))
    with tqdm(total=total_files, desc="Processing cover art files") as pbar:
        for root, _, files in os.walk(path):
            for file in files:
                rename_cover_art(os.path.join(root, file), hide)
                pbar.update(1)

# Info command function
def analyze_audio(path: str, output, show_progress: bool = True):
    """Analyze audio file properties and write to output.
    Args:
        path (str): File or directory to analyze.
        output: File-like object to write results (e.g., sys.stdout or file).
        show_progress (bool): If True, use tqdm progress bar.
    """
    if not shutil.which('ffprobe'):
        print("ffprobe is not found. Please install FFmpeg and ensure ffprobe is in your PATH.")
        return

    # Gather audio files
    if os.path.isfile(path) and os.path.splitext(path)[1].lower() in AUDIO_EXTENSIONS:
        audio_files = [Path(path)]
    elif os.path.isdir(path):
        audio_files = [p for ext in AUDIO_EXTENSIONS for p in Path(path).rglob("*" + ext)]
        if not audio_files:
            print("No audio files found in the specified directory.")
            return
    else:
        print(f"{path} is neither a valid file nor directory.")
        return

    # Choose iterator based on progress display
    audio_files_iter = tqdm(audio_files, desc="Analyzing audio files") if show_progress else audio_files

    for audio_file in audio_files_iter:
        output.write(f"Analyzing: {audio_file}\n")
        try:
            cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(audio_file)]
            data = json.loads(subprocess.check_output(cmd, universal_newlines=True))
            stream = data["streams"][0]
            codec_name = stream.get("codec_name", "N/A")
            sample_rate = stream.get("sample_rate", "N/A")
            channels = stream.get("channels", "N/A")
            bit_depth = stream.get("bits_per_raw_sample", "N/A")
            bit_rate = data["format"].get("bit_rate", "N/A")
            channel_info = {1: "Mono", 2: "Stereo"}.get(channels, f"{channels} channels") if channels != "N/A" else "N/A"

            output.write(f"  Bitrate: {bit_rate} bps\n" if bit_rate != "N/A" else "  Bitrate: N/A\n")
            output.write(f"  Sample Rate: {sample_rate} Hz\n" if sample_rate != "N/A" else "  Sample Rate: N/A\n")
            output.write(f"  Bit Depth: {bit_depth} bits\n" if bit_depth != "N/A" else "  Bit Depth: N/A\n")
            output.write(f"  Channels: {channel_info}\n")
            output.write(f"  Codec: {codec_name}\n")

            if audio_file.suffix == ".m4a":
                if "aac" in codec_name.lower():
                    output.write("  [INFO] This is an AAC (lossy) file.\n")
                elif "alac" in codec_name.lower():
                    output.write("  [INFO] This is an ALAC (lossless) file.\n")
                else:
                    output.write(f"  [WARNING] Unknown codec: {codec_name}\n")
            elif audio_file.suffix in [".opus", ".mp3"]:
                output.write(f"  [INFO] This is a lossy file: {codec_name}\n")
            if bit_depth != "N/A" and int(bit_depth) < 16:
                output.write("  [WARNING] Potential lossy encoding: Low bit depth\n")
            if sample_rate != "N/A" and int(sample_rate) < 44100:
                output.write("  [WARNING] Potential lossy encoding: Low sample rate\n")
            output.write("\n")
        except Exception as e:
            output.write(f"  [ERROR] {str(e)}\n")

# Main function
def main():
    """Handle command-line arguments and execute subcommands.
    Notes:
        - Sets up argparse with three subcommands.
        - Manages execution flow based on user input.
    """
    parser = argparse.ArgumentParser(description="Audio file utilities")
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to run", required=True)

    # Check subcommand setup
    check_parser = subparsers.add_parser("check", help="Check integrity of audio files")
    check_parser.add_argument("path", type=path_type, help="Path to file or directory")
    check_parser.add_argument("--verbose", action="store_true", help="Output to console without progress bar")
    check_parser.add_argument("--save-log", action="store_true", help="Save log file when using --verbose")

    # Cover-art subcommand setup
    cover_art_parser = subparsers.add_parser("cover-art", help="Hide or show cover art files")
    cover_art_group = cover_art_parser.add_mutually_exclusive_group(required=True)
    cover_art_group.add_argument("--hide", action="store_true", help="Hide cover art files")
    cover_art_group.add_argument("--show", action="store_true", help="Show cover art files")
    cover_art_parser.add_argument("path", type=directory_path, help="Directory to process")

    # Info subcommand setup
    info_parser = subparsers.add_parser("info", help="Get audio file information")
    info_parser.add_argument("path", type=path_type, help="Path to file or directory")
    info_parser.add_argument("-o", "--output", default="audio_analysis.txt", help="Output file name")
    info_parser.add_argument("--verbose", action="store_true", help="Output to console without progress bar")

    args = parser.parse_args()

    if args.command == "check":
        verbose = args.verbose
        save_log = args.save_log if verbose else True  # Log saved by default unless verbose overrides
        check_integrity(args.path, verbose=verbose, save_log=save_log)
    elif args.command == "cover-art":
        process_cover_art(args.path, args.hide)
    elif args.command == "info":
        if args.verbose:
            analyze_audio(args.path, sys.stdout, show_progress=False)
        else:
            output_file = f"audio_analysis_{datetime.datetime.now().strftime('%Y%m%d')}.txt" if args.output == "audio_analysis.txt" else args.output
            with open(output_file, "w") as outfile:
                analyze_audio(args.path, outfile, show_progress=True)
            print(f"Analysis complete. Results saved to {output_file}")

if __name__ == "__main__":
    main()  # Run the script
