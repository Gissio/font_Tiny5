"""
bdf2ufo

Converts a .bdf pixel font to a .ufo variable vector font.

(C) 2024-2026 Gissio
License: MIT
"""

import argparse
import logging
import yaml

from .bdf_font import BDFFont
from .designspace import DesignSpace

# Definitions

BDF2UFO_VERSION = "1.1"


def auto_int(x: str) -> int:
    """Convert a string to an integer, auto-detecting the base (hex, octal, decimal)."""
    return int(x, 0)


# Main entry point

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _setup_argument_parser() -> argparse.ArgumentParser:
    """Set up and return the argument parser for bdf2ufo."""
    parser = argparse.ArgumentParser(
        prog="bdf2ufo",
        description="Converts .bdf pixel fonts to .ufo static and variable vector fonts.",
    )

    # Version and verbosity
    parser.add_argument(
        "-V", "--version", action="version", version=f"bdf2ufo {BDF2UFO_VERSION}"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="verbose mode")

    # Configuration options
    parser.add_argument("-c", "--config", help="path to a YAML configuration file")

    # Positional arguments
    parser.add_argument("input", help="the .bdf file to be converted")
    parser.add_argument("output", help="the masters folder with the built .ufo files")

    return parser


def main():
    """Convert a .bdf pixel font to a .ufo variable vector font."""
    parser = _setup_argument_parser()
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Load configuration
    logger.info("Loading configuration")
    config = {}
    if args.config:
        try:
            with open(args.config, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        except (IOError, yaml.YAMLError) as e:
            logger.error("Failed to load configuration file: %s", e)
            return

    # Load BDF font
    logger.info("Loading BDF font")
    try:
        bdf_font = BDFFont()

        bdf_font.load(args.input, config)
    except (IOError, ValueError, OSError) as e:
        logger.error("Failed to load BDF font: %s", e)
        return

    # Setup and build designspace
    logger.info("Building designspace")
    try:
        designspace = DesignSpace()

        designspace.setup(bdf_font, config)

        designspace.build(args.output)
    except ValueError as e:
        logger.error("Failed to build designspace: %s", e)
        return

    logger.info("Done")


if __name__ == "__main__":
    main()
