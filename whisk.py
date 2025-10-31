#! /usr/bin/env python3
#
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

import argparse
import itertools
import json
import jsonschema
import os
import pathlib
import string
import subprocess
import sys
import tabulate
import textwrap
import tqdm
import yaml
import re
from enum import Enum
from collections import namedtuple

tabulate.PRESERVE_WHITESPACE = True

THIS_DIR = pathlib.Path(__file__).parent.absolute()
SCHEMA_FILE = THIS_DIR / "whisk.schema.json"

CACHE_VERSION = 1


class OEVersion(object):
    def __init__(
        self,
        conf_version,
        *,
        append_sep=":",
        basehash_ignore_vars="BB_BASEHASH_IGNORE_VARS",
        env_passthrough_var="BB_ENV_PASSTHROUGH_ADDITIONS",
    ):
        self.conf_version = conf_version
        self.append_sep = append_sep
        self.basehash_ignore_vars = basehash_ignore_vars
        self.env_passthrough_var = env_passthrough_var


VERSION_COMPAT = {
    "morty": OEVersion(
        1,
        append_sep="_",
        basehash_ignore_vars="BB_HASHBASE_WHITELIST",
        env_passthrough_var="BB_ENV_EXTRAWHITE",
    ),
    "pyro": OEVersion(
        1,
        append_sep="_",
        basehash_ignore_vars="BB_HASHBASE_WHITELIST",
        env_passthrough_var="BB_ENV_EXTRAWHITE",
    ),
    "rocko": OEVersion(
        1,
        append_sep="_",
        basehash_ignore_vars="BB_HASHBASE_WHITELIST",
        env_passthrough_var="BB_ENV_EXTRAWHITE",
    ),
    "sumo": OEVersion(
        1,
        append_sep="_",
        basehash_ignore_vars="BB_HASHBASE_WHITELIST",
        env_passthrough_var="BB_ENV_EXTRAWHITE",
    ),
    "thud": OEVersion(
        1,
        append_sep="_",
        basehash_ignore_vars="BB_HASHBASE_WHITELIST",
        env_passthrough_var="BB_ENV_EXTRAWHITE",
    ),
    "warrior": OEVersion(
        1,
        append_sep="_",
        basehash_ignore_vars="BB_HASHBASE_WHITELIST",
        env_passthrough_var="BB_ENV_EXTRAWHITE",
    ),
    "zeus": OEVersion(
        1,
        append_sep="_",
        basehash_ignore_vars="BB_HASHBASE_WHITELIST",
        env_passthrough_var="BB_ENV_EXTRAWHITE",
    ),
    "dunfell": OEVersion(
        1,
        append_sep="_",
        basehash_ignore_vars="BB_HASHBASE_WHITELIST",
        env_passthrough_var="BB_ENV_EXTRAWHITE",
    ),
    "gatesgarth": OEVersion(
        1,
        append_sep="_",
        basehash_ignore_vars="BB_HASHBASE_WHITELIST",
        env_passthrough_var="BB_ENV_EXTRAWHITE",
    ),
    "hardknott": OEVersion(
        1,
        append_sep="_",
        basehash_ignore_vars="BB_HASHBASE_WHITELIST",
        env_passthrough_var="BB_ENV_EXTRAWHITE",
    ),
    "honister": OEVersion(
        1,
        basehash_ignore_vars="BB_HASHBASE_WHITELIST",
        env_passthrough_var="BB_ENV_EXTRAWHITE",
    ),
    "kirkstone": OEVersion(2),
    "langdale": OEVersion(2),
}

LATEST_COMPAT = OEVersion(2)


class ConfTemplate(string.Template):
    delimiter = r"%"


def get_layerseries_corenames(version):
    for layer in version.get("layers", []):
        for layer_path in [pathlib.Path(p) for p in layer.get("paths", [])]:
            conf_file = layer_path / "conf" / "layer.conf"
            if conf_file.exists():
                with conf_file.open("r") as f:
                    for line in f:
                        m = re.match(r'^LAYERSERIES_CORENAMES *= *"(.*)"', line)
                        if m is not None:
                            return m.group(1).split()

    return []


def print_items(items, is_current, extra=[]):
    def get_current(i):
        if is_current(i):
            return " *"
        return "  "

    print(
        tabulate.tabulate(
            [
                (
                    get_current(i),
                    i,
                    items[i].get("description", ""),
                )
                for i in sorted(items)
            ]
            + [(get_current(e), e, "") for e in extra],
            tablefmt="plain",
        )
    )


def print_modes(conf, cur_mode):
    print_items(conf["modes"], lambda m: m == cur_mode)


def print_sites(conf, cur_site):
    print_items(conf["sites"], lambda s: s == cur_site)


def print_products(conf, cur_product):
    print_items(conf["products"], lambda p: p == cur_product)


def print_versions(conf, cur_version):
    print_items(conf["versions"], lambda v: v == cur_version, extra=["default"])


def write_hook(f, conf, hook):
    f.write(conf.get("hooks", {}).get(hook, ""))
    f.write("\n")


def parse_conf_file(path):
    with path.open("r") as f:
        conf_str = f.read()

    conf = yaml.load(conf_str, Loader=yaml.Loader)

    if not "version" in conf:
        print("Config file '%s' missing version" % sys_args.conf)
        return (None, None)

    if conf["version"] < 1 or conf["version"] > 2:
        print("Bad version %r in config file '%s'" % (conf["version"], path))
        return (None, None)

    project_root = path.parent / conf.get("project_root", ".")

    # Re-parse, expanding variables
    env = os.environ.copy()
    env["WHISK_PROJECT_ROOT"] = project_root.absolute()
    conf = yaml.load(conf_str, Loader=yaml.Loader)

    # Recursively do environment substitution on all strings
    def substitute(item):
        if isinstance(item, dict):
            for k in item:
                item[k] = substitute(item[k])
            return item
        elif isinstance(item, list):
            for i in range(0, len(item)):
                item[i] = substitute(item[i])
            return item
        elif isinstance(item, str):
            # Throws a KeyError (handled by the caller) if the string contains
            # an attempted dereference to an undefined environment variable.
            return ConfTemplate(item).substitute(**env)
        else:
            return item

    try:
        conf = substitute(conf)
    except KeyError as e:
        print("Couldn't substitute all environment variables (%s is undefined)." % e)
        return (None, None)

    try:
        with SCHEMA_FILE.open("r") as f:
            jsonschema.validate(conf, json.load(f))
    except jsonschema.ValidationError as e:
        print("Error validating %s: %s" % (path, e.message))
        return (None, None)

    return (conf, project_root)


def configure(sys_args):
    parser = argparse.ArgumentParser(description="Configure build")
    parser.add_argument("--product", help="Change build product")
    parser.add_argument("--mode", help="Change build mode")
    parser.add_argument("--site", help="Change build site")
    parser.add_argument("--version", help="Set Yocto version")
    parser.add_argument("--build-dir", help="Set build directory")
    parser.add_argument("--list", action="store_true", help="List options")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write out new config files (useful if product configuration has changed)",
    )
    parser.add_argument(
        "--no-config",
        "-n",
        action="store_true",
        help="Ignore cached user configuration",
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true", help="Suppress non-error output"
    )
    parser.add_argument("--fetch", action="store_true", help="Fetch required layers")
    parser.add_argument("--no-pyrex", action="store_true", help="Do not use Pyrex")

    user_args = parser.parse_args(sys_args.user_args)

    (conf, project_root) = parse_conf_file(sys_args.conf)
    if not conf:
        return 1

    def get_product(name):
        nonlocal conf
        if name == "core":
            return conf.get("core", {})
        return conf["products"][name]

    def get_subproducts(name):
        p = get_product(name)
        subproducts = p.get("subproducts")
        if not subproducts:
            subproducts = {name: dict()}
        return subproducts

    cache_path = pathlib.Path(conf.get("cache", project_root / ".config.yaml"))
    cache = {}
    if not user_args.no_config:
        try:
            with cache_path.open("r") as f:
                cache = yaml.load(f, Loader=yaml.Loader)
        except OSError:
            pass

        try:
            if cache.get("cache_version") != CACHE_VERSION:
                cache = {}
        except AttributeError:
            cache = {}

    defaults = conf.get("defaults", {})

    cur_mode = cache.get("mode", defaults.get("mode"))
    cur_product = cache.get("product", defaults.get("product"))
    cur_site = cache.get("site", defaults.get("site"))
    cur_version = cache.get("version", "default")
    cur_actual_version = cache.get("actual_version", "")
    build_dir = pathlib.Path(cache.get("build_dir", defaults.get("build_dir", "build")))

    write = user_args.write or sys_args.init

    if user_args.list:
        print("Possible products:")
        print_products(conf, cur_product)
        print("Possible modes:")
        print_modes(conf, cur_mode)
        print("Possible sites:")
        print_sites(conf, cur_site)
        print("Possible versions:")
        print_versions(conf, cur_version)
        return 0

    if user_args.product:
        write = True
        if not user_args.product in conf.get("products", {}):
            print("Unknown product '%s'. Please choose from:" % user_args.product)
            print_products(conf, cur_product)
            return 1
        cur_product = user_args.product

    if user_args.mode:
        write = True
        if user_args.mode not in conf["modes"]:
            print("Unknown mode '%s'. Please choose from:" % user_args.mode)
            print_modes(conf, cur_mode)
            return 1
        cur_mode = user_args.mode

    if user_args.site:
        write = True
        if user_args.site not in conf["sites"]:
            print("Unknown site '%s'. Please choose from:" % user_args.site)
            print_sites(conf, cur_site)
            return 1
        cur_site = user_args.site

    if user_args.version:
        write = True
        if sys_args.init:
            if (
                user_args.version != "default"
                and user_args.version not in conf["versions"]
            ):
                print("Unknown version '%s'. Please choose from:" % user_args.version)
                print_versions(conf, cur_version)
                return 1

            cur_version = user_args.version
        elif user_args.version != cur_version:
            print(
                "The version cannot be changed after the environment is initialized. Please initialize a new environment with '--version=%s'"
                % user_args.version
            )
            return 1

    if user_args.build_dir:
        if not sys_args.init:
            print(
                "Build directory cannot be changed after environment is initialized. Please initialize a new environment with '--build-dir=%s'"
                % user_args.build_dir
            )
            return 1
        build_dir = pathlib.Path(user_args.build_dir)

    if not cur_product:
        print("A product must be specified with --product")
        return 1

    if not cur_mode:
        print("A build mode must be specified with --mode")
        return 1

    if not cur_site:
        print("A site must be specified with --site")
        return 1

    # Set the actual version
    if cur_version == "default":
        product_version = conf["products"][cur_product]["default_version"]

        if sys_args.init or product_version == cur_actual_version:
            # Environment hasn't been initialized or it's not changing, so
            # it can be set
            cur_actual_version = product_version
        else:
            print(
                "Build environment is configured to build version '{actual}' and cannot be changed to version '{v}' required to build products: {product}. Please initialize a new environment with `--product={product} --version=default`".format(
                    actual=cur_actual_version,
                    v=product_version,
                    product=cur_product,
                )
            )
            return 1
    else:
        cur_actual_version = cur_version

    version = conf["versions"][cur_actual_version]

    cur_layers_paths = {
        l["name"]: l.get("paths", []) for l in version.get("layers", [])
    }
    cur_layers_bbmasks = {
        l["name"]: l.get("bbmask", []) for l in version.get("layers", [])
    }

    # Sanity check that if any selected product does not support multiconfig,
    # it is the only selected product.
    using_multiconfig = conf["products"][cur_product].get("multiconfig_enabled", True)
    if not using_multiconfig:
        multiconfigs = conf["products"][cur_product].get("multiconfigs", [])
        if len(multiconfigs) > 0:
            print(
                "Product '{product}' does not support multiconfig, but its 'multiconfig' attribute has some elements: {multiconfigs}.".format(
                    product=cur_product, multiconfigs=multiconfigs
                )
            )
            return 1

        if "subproducts" in conf["products"][cur_product]:
            print(
                "Product '{product}' cannot have subproducts since it does not support multiconfig"
            )
            return 1

    # Sanity check that all configured products have layers
    for p in ["core", cur_product]:
        missing = set(
            l for l in get_product(p).get("layers", []) if not l in cur_layers_paths
        )
        if missing:
            print(
                "Product '{product}' requires layer collection(s) '{layers}' which is not present in version '{version}'".format(
                    product=p, layers=" ".join(missing), version=cur_actual_version
                )
            )
            return 1

    # Check for duplicated subproducts
    seen_subproducts = {}
    for name in conf["products"].keys():
        for p in get_subproducts(name):
            seen_subproducts.setdefault(p, []).append(name)

        for k, v in seen_subproducts.items():
            if len(v) > 1:
                print(
                    "Subproduct '{p}' defined in multiple products: {products}".format(
                        p=k, products=", ".join(v)
                    )
                )
                return 1

    requested_layers = set()
    for name in ["core", cur_product]:
        requested_layers.update(get_product(name).get("layers", []))

    if user_args.fetch:
        fetch_commands = []
        for o in [conf, version] + [
            l for l in version.get("layers", []) if l["name"] in requested_layers
        ]:
            fetch_commands.extend(o.get("fetch", {}).get("commands", []))

        env = os.environ.copy()
        env["WHISK_PROJECT_ROOT"] = project_root.absolute()

        for c in tqdm.tqdm(
            fetch_commands,
            desc="Fetching",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
            disable=user_args.quiet,
        ):
            r = subprocess.run(
                c,
                shell=True,
                cwd=project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
            )
            if r.returncode:
                print("Fetch command '%s' failed:\n%s" % (c, r.stdout))
                return 1

    compat_name = version.get("compat", "auto")
    if compat_name == "auto":
        corenames = get_layerseries_corenames(version)
        if corenames:
            for c in corenames:
                if c in VERSION_COMPAT:
                    compat_name = c
                    break
            else:
                # Version unknown. Assume the latest (no compat flags)
                compat_name = ""
        else:
            # No LAYERSERIES_CORENAMES. Assume "pyro" since it is was the last
            # version to not have one
            compat_name = "pyro"

    compat = VERSION_COMPAT.get(compat_name, LATEST_COMPAT)

    with sys_args.env.open("w") as f:
        f.write(
            textwrap.dedent(
                f"""\
                export WHISK_CONF_PRODUCT="{cur_product}"
                export WHISK_SUBPRODUCTS="{' '.join(sorted(get_subproducts(cur_product).keys()))}"
                # Deprecated
                export WHISK_PRODUCTS="$WHISK_SUBPRODUCTS"
                export WHISK_MODE="{cur_mode}"
                export WHISK_SITE="{cur_site}"
                export WHISK_VERSION="{cur_version}"
                export WHISK_ACTUAL_VERSION="{cur_actual_version}"

                export WHISK_BUILD_DIR={str(build_dir.absolute())}
                export WHISK_INIT={'true' if sys_args.init else 'false'}
                export WHISK_COMPAT="{compat_name}"
                """
            )
        )

        write_hook(f, conf, "pre_init")
        if sys_args.init:
            bitbake_dir = version.get("bitbakedir")
            if bitbake_dir:
                f.write('export BITBAKEDIR="%s"\n' % bitbake_dir)

            f.write(
                textwrap.dedent(
                    """\
                    export WHISK_PROJECT_ROOT="{root}"
                    export {env_passthrough_var}="${{{env_passthrough_var}}} {passthrough_vars} WHISK_PROJECT_ROOT WHISK_CONF_PRODUCT WHISK_PRODUCTS WHISK_MODE WHISK_SITE WHISK_ACTUAL_VERSION"
                    PATH="{this_dir}/bin:$PATH"
                    """
                ).format(
                    passthrough_vars=" ".join(
                        conf.get("hooks", {}).get("env_passthrough_vars", [])
                    ),
                    env_passthrough_var=compat.env_passthrough_var,
                    root=project_root.absolute(),
                    this_dir=THIS_DIR,
                )
            )

            if version.get("pyrex") and not user_args.no_pyrex:
                f.write(
                    textwrap.dedent(
                        """\
                        PYREX_CONFIG_BIND="{root}"
                        PYREX_ROOT="{version[pyrex][root]}"
                        PYREX_OEINIT="{version[oeinit]}"
                        PYREXCONFFILE="{version[pyrex][conf]}"

                        . {version[pyrex][root]}/pyrex-init-build-env $WHISK_BUILD_DIR
                        """
                    ).format(
                        root=project_root.absolute(),
                        version=version,
                    )
                )

            else:
                f.write(
                    ". {version[oeinit]} $WHISK_BUILD_DIR\n".format(version=version)
                )

        write_hook(f, conf, "post_init")

        f.write("unset WHISK_BUILD_DIR WHISK_INIT\n")

    if not user_args.no_config:
        with cache_path.open("w") as f:
            f.write(
                yaml.dump(
                    {
                        "cache_version": CACHE_VERSION,
                        "mode": cur_mode,
                        "product": cur_product,
                        "site": cur_site,
                        "version": cur_version,
                        "actual_version": cur_actual_version,
                        "build_dir": str(build_dir.absolute()),
                    },
                    Dumper=yaml.Dumper,
                )
            )

    if write:
        (build_dir / "conf").mkdir(parents=True, exist_ok=True)

        with (build_dir / "conf" / "site.conf").open("w") as f:
            f.write("# This file was dynamically generated by whisk\n")
            f.write(f'CONF_VERSION = "{compat.conf_version}"\n\n')

            f.write(conf["sites"][cur_site].get("conf", ""))
            f.write("\n")
            f.write(conf["modes"][cur_mode].get("conf", ""))
            f.write("\n")

            if conf["version"] < 2:
                f.write(
                    textwrap.dedent(
                        """\
                        DEPLOY_DIR_BASE ?= "${TOPDIR}/deploy/${WHISK_MODE}/${WHISK_ACTUAL_VERSION}"
                        WHISK_DEPLOY_DIR_BASE ?= "${DEPLOY_DIR_BASE}"

                        WHISK_DEPLOY_DIR_core = "${WHISK_DEPLOY_DIR_BASE}/core"
                        DEPLOY_DIR_core = "${WHISK_DEPLOY_DIR_core}"
                        """
                    )
                )
            else:
                f.write(
                    textwrap.dedent(
                        """\
                        WHISK_DEPLOY_DIR_BASE ?= "${TOPDIR}/deploy/${WHISK_MODE}/${WHISK_ACTUAL_VERSION}"

                        WHISK_DEPLOY_DIR_core = "${WHISK_DEPLOY_DIR_BASE}/core"
                        """
                    )
                )

            f.write(
                textwrap.dedent(
                    """\
                    BBPATH .= ":${TOPDIR}/whisk"

                    WHISK_CURRENT_PRODUCT ?= "core"

                    # Deprecated variables
                    WHISK_PRODUCT = "${WHISK_CURRENT_PRODUCT}"
                    WHISK_PRODUCT_DESCRIPTION = "${WHISK_CURRENT_PRODUCT_DESCRIPTION}"

                    # Set TMPDIR to a version specific location
                    TMPDIR_BASE ?= "${TOPDIR}/tmp/${WHISK_MODE}/${WHISK_ACTUAL_VERSION}"

                    TMPDIR = "${TMPDIR_BASE}/${WHISK_CURRENT_PRODUCT}"

                    # Set the deploy directory to output to a well-known location
                    DEPLOY_DIR = "${WHISK_DEPLOY_DIR_${WHISK_CURRENT_PRODUCT}}"
                    DEPLOY_DIR_IMAGE = "${DEPLOY_DIR}/images"

                    WHISK_TARGETS_core = ""
                    """
                )
            )
            f.write('WHISK_TARGETS = "${WHISK_TARGETS_%s}"\n' % cur_product)

            if conf["version"] < 2:
                f.write(
                    'DEPLOY_DIR_{p} = "${{WHISK_DEPLOY_DIR_{p}}}"\n'.format(
                        p=cur_product
                    )
                )

            f.write(
                'WHISK_TARGETS_{p} = "{targets}"\n'.format(
                    p=cur_product,
                    targets=" ".join(
                        sorted(conf["products"][cur_product].get("targets", []))
                    ),
                )
            )

            for name in sorted(get_subproducts(cur_product).keys()):
                f.write(
                    'WHISK_DEPLOY_DIR_{name} = "${{WHISK_DEPLOY_DIR_BASE}}/{name}"\n'.format(
                        name=name
                    )
                )

            f.write("\n")

            # Only set up Bitbake multiconfig if the selected Whisk products
            # support it.
            if using_multiconfig:
                multiconfigs = set(
                    conf["products"][cur_product].get("multiconfigs", [])
                )
                for name in get_subproducts(cur_product).keys():
                    multiconfigs.add("product-%s" % name)

                f.write(
                    textwrap.dedent(
                        """\
                        BBMULTICONFIG = "{multiconfigs}"
                        """
                    ).format(multiconfigs=" ".join(sorted(multiconfigs)))
                )

            f.write(
                f'{compat.basehash_ignore_vars}{compat.append_sep}append = " WHISK_PROJECT_ROOT"\n'
            )

            f.write(conf.get("core", {}).get("conf", ""))
            f.write("\n")

            # If the selected whisk product is not using multiconfig, then
            # force all the configuration bits Whisk would normally assign
            # to the product MC, into the base conf.
            #
            # Do this by forcibly injecting the product-<name>.conf file
            # in Whisk's conf/multiconfig directory, at the very bottom
            # of site.conf.
            if not using_multiconfig:
                f.write(
                    textwrap.dedent(
                        """\
                        # Multiconfig not enabled. Insert all product-
                        # specific info into base configuration.
                        require conf/multiconfig/product-{product}.conf
                        """
                    ).format(product=cur_product)
                )
                f.write("\n")

        mc_dir = build_dir / "whisk" / "conf" / "multiconfig"
        mc_dir.mkdir(parents=True, exist_ok=True)
        for name, p in conf["products"].items():
            for sub_name, sub_p in get_subproducts(name).items():
                with (mc_dir / ("product-%s.conf" % sub_name)).open("w") as f:
                    f.write(
                        textwrap.dedent(
                            """\
                            # This file was dynamically generated by whisk
                            WHISK_CURRENT_PRODUCT = "{product}"
                            WHISK_CURRENT_PRODUCT_DESCRIPTION = "{description}"

                            """
                        ).format(
                            product=sub_name,
                            description=sub_p.get(
                                "description", p.get("description", "")
                            ),
                        )
                    )

                    f.write(p.get("conf", ""))
                    f.write("\n")
                    f.write(sub_p.get("conf", ""))
                    f.write("\n")

        with (build_dir / "conf" / "bblayers.conf").open("w") as f:
            f.write(
                textwrap.dedent(
                    """\
                    # This file was dynamically generated by whisk
                    BBPATH = "${TOPDIR}"
                    BBFILES ?= ""

                    """
                )
            )

            for l in version.get("layers", []):
                if l["name"] in requested_layers:
                    for p in l.get("paths", []):
                        f.write('BBLAYERS += "%s"\n' % p)
                    for m in l.get("bbmask", []):
                        f.write('BBMASK += "%s"\n' % m)

            f.write('BBLAYERS += "%s/meta-whisk"\n\n' % THIS_DIR)

            f.write("%s\n" % conf.get("core", {}).get("layerconf", ""))

            f.write(
                textwrap.dedent(
                    """\
                    # This line gives devtool a place to add its layers
                    BBLAYERS += ""
                    """
                )
            )

    if write and not sys_args.init:
        return 0

    if not user_args.quiet:
        print("PRODUCT    = %s" % cur_product)
        print("MODE       = %s" % cur_mode)
        print("SITE       = %s" % cur_site)
        print("VERSION    = %s" % cur_version, end="")
        if cur_version != cur_actual_version:
            print(" (%s)" % cur_actual_version)
        else:
            print()

    return 0


def validate(args):
    import yamllint.linter
    import yamllint.config

    ret = 0

    try:
        with args.conf.open("r") as f, SCHEMA_FILE.open("r") as schema:
            jsonschema.validate(yaml.load(f, Loader=yaml.Loader), json.load(schema))
    except jsonschema.ValidationError as e:
        print(e)
        ret = 1

    if parse_conf_file(args.conf) == (None, None):
        ret = 1

    config = yamllint.config.YamlLintConfig(
        textwrap.dedent(
            """\
            extends: default
            rules:
                # Long lines are fine
                line-length: disable
            """
        )
    )

    ret = 0
    with args.conf.open("r") as f:
        for p in yamllint.linter.run(f, config, str(args.conf)):
            print("%r" % p)
            ret = 1

    return ret


def main():
    parser = argparse.ArgumentParser(description="Whisk product manager")

    subparser = parser.add_subparsers(dest="command")
    subparser.required = True

    configure_parser = subparser.add_parser(
        "configure", help="Configure build environment"
    )

    configure_parser.add_argument(
        "--conf", help="Project configuration file", type=pathlib.Path
    )
    configure_parser.add_argument(
        "--init", action="store_true", help="Run first-time initialization"
    )
    configure_parser.add_argument(
        "--env", help="Path to environment output file", type=pathlib.Path
    )
    configure_parser.add_argument("user_args", nargs="*", help="User arguments")
    configure_parser.set_defaults(func=configure)

    validate_parser = subparser.add_parser(
        "validate", help="Validate configuration file"
    )
    validate_parser.add_argument(
        "conf", help="configuration file to validate", type=pathlib.Path
    )
    validate_parser.set_defaults(func=validate)

    args = parser.parse_args()

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
