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
# This class lets you define a "deploy alias"; that is a command that doesn't
# build anything itself, but cross-links a deliverable from one multiconfig
# deploy directory to another
#
# The class is controlled by the DEPLOY_ALIASES variable. It specifies
# a space separated list of what deployed artifact aliases should be copied.
# Each item is in the form:
#
#   mc:MULTICONFIG:RECIPE:TASK:PATH
#
# Where:
#
# MULTICONFIG - The name of the source multiconfig
# RECIPE - The source recipe that produces the artifact
# TASK - The source task that produces the artifact (e.g. do_deploy,
#   do_image_complete, etc.)
# PATH - The path to the artifact that should be copied


LICENSE = "MIT"

DEPLOY_ALIASES ?= ""

INHIBIT_DEFAULT_DEPS = "1"

PACKAGE_ARCH = "all"

DEPCHAIN_DBGDEFAULTDEPS = "1"

inherit nopackages allarch deploy

deltask do_fetch
deltask do_unpack
deltask do_patch
deltask do_configure
deltask do_compile
deltask do_install
deltask do_populate_sysroot
deltask do_populate_lic

def get_mcdepends(d):
    aliases = d.getVar('DEPLOY_ALIASES')

    mcdepends = []
    for a in aliases.split():
        if not a.startswith('mc:'):
            continue

        (_, mc, pn, task, _) = a.split(':')
        mcdepends.append("mc::%s:%s:%s" % (mc, pn, task))

    return ' '.join(sorted(mcdepends))

python do_deploy() {
    aliases = d.getVar('DEPLOY_ALIASES')
    for a in aliases.split():
        (_, _, _, _, src) = a.split(':')

        filename = os.path.basename(src)
        dst = "%s/%s" % (d.getVar('DEPLOYDIR'), filename)

        if os.path.islink(src):
            real_src = os.path.realpath(src)
            real_filename = os.path.basename(real_src)
            real_dst = "%s/%s" % (d.getVar('DEPLOYDIR'), real_filename)

            oe.path.copyhardlink(real_src, real_dst)
            os.symlink(real_filename, dst)
        else:
            oe.path.copyhardlink(src, dst)
}
do_deploy[mcdepends] = "${@get_mcdepends(d)}"
do_deploy[cleandirs] = "${DEPLOYDIR}"
addtask do_deploy after do_compile before do_build
