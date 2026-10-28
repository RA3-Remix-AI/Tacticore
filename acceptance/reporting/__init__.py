"""Offline, read-only evidence indexing. This package never grants game authority."""

from .bundle import BundleError, build_review_bundle

__all__ = ["BundleError", "build_review_bundle"]
