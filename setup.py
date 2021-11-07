"""
Setup, package, and build file for the bcl cryptography library.
"""
import sys
import platform
import os
import os.path
import shutil
import glob
import subprocess
import tarfile
import errno
import urllib.request
from distutils.sysconfig import get_config_vars
from setuptools import Distribution, setup
from setuptools.command.build_ext import build_ext as _build_ext

try:
    from setuptools.command.build_clib import build_clib as _build_clib
except ImportError:
    from distutils.command.build_clib import build_clib as _build_clib

def prepare_libsodium_source_tree():
    """
    Retrieve the libsodium source archive and extract it
    to the location used by the build process.
    """
    # URL from which libsodium source archive is retrieved,
    # and paths into which it is extracted and then moved.
    url = (
        'https://github.com/jedisct1/libsodium/releases' + \
        '/download/1.0.18-RELEASE/libsodium-1.0.18.tar.gz'
    )
    libsodium_tar_gz_path = './bcl/libsodium.tar.gz'
    libsodium_tar_gz_folder = './bcl/libsodium_tar_gz'
    libsodium_folder = './bcl/libsodium'

    # Download the source archive to a local path (unless
    # it is already present).
    if not os.path.exists(libsodium_tar_gz_path):
        try:
            urllib.request.urlretrieve(url, filename=libsodium_tar_gz_path)
        except:
            raise RuntimeError(
                'failed to download libsodium archive and no local ' + \
                'archive was found at `' + libsodium_tar_gz_path + '`'
            ) from None

    # Extract the archive into a temporary folder (removing
    # the folder if it already exists).
    with tarfile.open(libsodium_tar_gz_path) as libsodium_tar_gz:
        if os.path.exists(libsodium_tar_gz_folder):
            shutil.rmtree(libsodium_tar_gz_folder)
        libsodium_tar_gz.extractall(libsodium_tar_gz_folder)

    # Move the source tree to the destination folder (removing
    # the destination folder first, if it already exists).
    if os.path.exists(libsodium_folder):
        shutil.rmtree(libsodium_folder)
    shutil.move(
        libsodium_tar_gz_folder + '/libsodium-1.0.18',
        libsodium_folder
    )

    # Remove the archive and temporary folder.
    os.remove(libsodium_tar_gz_path)
    shutil.rmtree(libsodium_tar_gz_folder)

class Distribution(Distribution):
    def has_c_libraries(self):
        # On Windows, only a precompiled dynamic library
        # file is used.
        return not sys.platform == "win32"

class build_clib(_build_clib):
    def get_source_files(self):
        files = glob.glob(os.path.relpath("bcl/libsodium/*"))
        files += glob.glob(os.path.relpath("bcl/libsodium/*/*"))
        files += glob.glob(os.path.relpath("bcl/libsodium/*/*/*"))
        files += glob.glob(os.path.relpath("bcl/libsodium/*/*/*/*"))
        files += glob.glob(os.path.relpath("bcl/libsodium/*/*/*/*/*"))
        files += glob.glob(os.path.relpath("bcl/libsodium/*/*/*/*/*/*"))
        files += glob.glob(os.path.relpath("bcl/libsodium/*/*/*/*/*/*/*"))
        return files

    def build_libraries(self, libraries):
        raise RuntimeError("`build_libraries` should not be invoked")

    def check_library_list(self, libraries):
        raise RuntimeError("`check_library_list` should not be invoked")

    def get_library_names(self):
        return ["sodium"]

    def run(self):
        # On Windows, only a precompiled dynamic library
        # file is used.
        if sys.platform == "win32":
            return

        # Retrieve (if necessary) and extract the libsodium source tree.
        prepare_libsodium_source_tree()

        # Use Python's build environment variables.
        build_env = {
            key: val
            for key, val in get_config_vars().items()
            if key in ("LDFLAGS", "CFLAGS", "CC", "CCSHARED", "LDSHARED")
            and key not in os.environ
        }
        os.environ.update(build_env)

        # Ensure the temporary build directory exists.
        build_temp = os.path.abspath(self.build_temp)
        try:
            os.makedirs(build_temp)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

        # Ensure that all executable files have the necessary permissions.
        prefix = 'bcl/libsodium/'
        for filename in [
            "autogen.sh", "compile", "configure", "depcomp", "install-sh",
            "missing", "msvc-scripts/process.bat", "test/default/wintest.bat",
        ]:
            os.chmod(os.path.relpath(prefix + filename), 0o755)

        # Confirm that make utility can be found.
        found = False
        if not os.environ.get("PATH", None) is None:
            for p in os.environ.get("PATH", "").split(os.pathsep):
                p = os.path.join(p, "make")
                if os.access(p, os.X_OK):
                    found = True
                for e in filter(
                    None,
                    os.environ.get("PATHEXT", "").split(os.pathsep)
                ):
                    if os.access(p + e, os.X_OK):
                        found = True
        if not found:
            raise RuntimeError("make utility cannot be found")

        # Determine location of libsodium configuration script and
        # configure libsodium.
        subprocess.check_call(
            [os.path.abspath(os.path.relpath("bcl/libsodium/configure"))] + \
            [
                "--disable-shared", "--enable-static",
                "--disable-debug", "--disable-dependency-tracking", "--with-pic",
            ] + \
            (["--disable-ssp"] if platform.system() == "SunOS" else []) + \
            ["--prefix", os.path.abspath(self.build_clib)],
            cwd=build_temp
        )

        make_args = os.environ.get("LIBSODIUM_MAKE_ARGS", "").split()

        # Build the library.
        subprocess.check_call(["make"] + make_args, cwd=build_temp)

        # Check the built library.
        subprocess.check_call(["make", "check"] + make_args, cwd=build_temp)

        # Install the built library.
        subprocess.check_call(["make", "install"] + make_args, cwd=build_temp)

class build_ext(_build_ext):
    def run(self):
        if self.distribution.has_c_libraries():
            build_clib = self.get_finalized_command("build_clib")
            self.include_dirs.append(os.path.join(build_clib.build_clib, "include"),)
            self.library_dirs.insert(0, os.path.join(build_clib.build_clib, "lib64"),)
            self.library_dirs.insert(0, os.path.join(build_clib.build_clib, "lib"),)

        return _build_ext.run(self)

with open("README.rst", "r") as fh:
    long_description = fh.read()

name = "bcl"
version = "2.0.0"

setup(
    name=name,
    version=version,
    license="MIT",
    url="https://github.com/nthparty/bcl",
    author="Nth Party, Ltd.",
    author_email="team@nthparty.com",
    description="Python library that provides a simple interface "+\
                "for symmetric (i.e., secret-key) and asymmetric "+\
                "(i.e., public-key) encryption/decryption primitives.",
    long_description=long_description,
    long_description_content_type="text/x-rst",
    test_suite="nose.collector",
    tests_require=["nose"],
    packages=["bcl"],
    ext_package="bcl",
    cffi_modules=["bcl/sodium_ffi.py:sodium_ffi"],
    cmdclass={
        "build_clib": build_clib,
        "build_ext": build_ext,
    },
    distclass=Distribution,
    zip_safe=False
)
