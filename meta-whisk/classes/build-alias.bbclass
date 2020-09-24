# 2020 Garmin Ltd. or its subsidiaries
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
#
# This class lets you define a "build alias"; that is a command that doesn't
# build anything itself, but depends on a set of other targets and causes them
# to build

LICENSE = "MIT"

TARGETS ?= ""

INHIBIT_DEFAULT_DEPS = "1"

PACKAGE_ARCH = "all"

DEPCHAIN_DBGDEFAULTDEPS = "1"

inherit nopackages allarch

deltask do_fetch
deltask do_unpack
deltask do_patch
deltask do_configure
deltask do_compile
deltask do_install
deltask do_populate_sysroot
deltask do_populate_lic

python() {
    depends = []
    mcdepends = []

    for t in (d.getVar('TARGETS') or '').split():
        if t.startswith('mc:'):
            _, mc, recipe = t.split(':')
            mcdepends.append("mc::%s:%s:do_build" % (mc, recipe))
        else:
            depends.append("%s:do_build" % t)

    # uniquify and sort
    depends = sorted(list(set(depends)))
    mcdepends = sorted(list(set(mcdepends)))

    d.setVarFlags("do_build", {
        "mcdepends": " ".join(mcdepends),
        "depends": " ".join(depends),
        "noexec": "1",
        "nostamp": "1",
    })
}

