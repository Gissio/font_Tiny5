"""
bdf2ufo

Converts a .bdf pixel font to a .ufo variable vector font.

(C) 2024-2026 Gissio
License: MIT
"""

import argparse
import logging
import sys

import yaml

from .bdf_font import BDFFont
from .designspace import DesignSpace

# Definitions

BDF2UFO_VERSION = "1.7"

# Main entry point

logging.basicConfig(level=logging.WARNING)
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
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="log the progress of the conversion"
    )

    # Configuration options
    parser.add_argument("-c", "--config", help="path to a YAML configuration file")

    # Positional arguments
    parser.add_argument("input", help="the .bdf file to be converted")
    parser.add_argument("output", help="the masters folder with the built .ufo files")

    return parser


def main() -> int:
    """Convert a .bdf pixel font to a .ufo variable vector font.

    Returns:
        The exit status: 0 on success, 1 on failure.
    """
    parser = _setup_argument_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)

    # Load configuration
    logger.info("Loading configuration")
    config = {}
    if args.config:
        try:
            with open(args.config, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        except (IOError, yaml.YAMLError) as e:
            logger.error("Failed to load configuration file: %s", e)
            return 1

    # Load BDF font
    logger.info("Loading BDF font")
    try:
        bdf_font = BDFFont()

        bdf_font.load(args.input, config)
    except (IOError, ValueError, OSError) as e:
        logger.error("Failed to load BDF font: %s", e)
        return 1

    # Setup and build designspace
    logger.info("Building designspace")
    try:
        designspace = DesignSpace()

        designspace.setup(bdf_font, config)

        designspace.build(args.output)
    except ValueError as e:
        logger.error("Failed to build designspace: %s", e)
        return 1

    logger.info("Done")

    return 0


if __name__ == "__main__":
    sys.exit(main())
