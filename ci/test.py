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

import os
import pathlib
import shutil
import subprocess
import tempfile
import textwrap
import unittest
import yaml

ROOT = pathlib.Path(__file__).parent.parent.absolute()


class WhiskTests(object):
    def setUp(self):
        self.project_root = ROOT / "test" / ("%d" % os.getpid()) / self.id()

        def cleanup_project():
            if self.project_root.is_dir():
                shutil.rmtree(self.project_root)

        self.addCleanup(cleanup_project)
        cleanup_project()
        self.project_root.mkdir(parents=True)

        os.symlink(ROOT / "init-build-env", self.project_root / "init-build-env")

        self.conf_file = self.project_root / "whisk.yaml"

    def write_conf(self, conf):
        with self.conf_file.open("w") as f:
            f.write(textwrap.dedent(conf))

    def append_conf(self, conf):
        with self.conf_file.open("a+") as f:
            f.write(textwrap.dedent(conf))

    def assertShellCode(self, fragment, capture_vars={}, env=None, success=True):
        (fd, log_file) = tempfile.mkstemp()
        self.addCleanup(lambda: os.unlink(log_file))
        os.close(fd)

        (fd, capture_file) = tempfile.mkstemp()
        self.addCleanup(lambda: os.unlink(capture_file))
        os.close(fd)

        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as f:
            f.write("set -eo pipefail\n")
            f.write(textwrap.dedent(fragment))
            f.write("\n")
            for v in capture_vars.keys():
                f.write('echo "%s=$%s" >> %s\n' % (v, v, capture_file))
            f.flush()

            if env is None:
                env = os.environ

            with open(log_file, "w") as log:
                p = subprocess.run(
                    ["/bin/bash", f.name],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    cwd=self.project_root,
                    env=env,
                )

        with open(log_file, "r") as log:
            if success:
                self.assertEqual(
                    p.returncode,
                    0,
                    "Process exited with non-zero exit code. Output:\n%s" % log.read(),
                )
            else:
                self.assertNotEqual(
                    p.returncode,
                    0,
                    "Process exited with zero exit code. Output:\n%s" % log.read(),
                )

        v = {}
        with open(capture_file, "r") as f:
            for line in f:
                line = line.rstrip()
                key, val = line.split("=", 1)
                v[key] = val

        self.assertDictEqual(v, capture_vars)

    def assertConfigVar(self, name, value):
        with self.conf_file.open("r") as f:
            data = yaml.load(f.read(), Loader=yaml.Loader)
            cache_file = pathlib.Path(
                data.get("cache", self.project_root / ".config.yaml")
            )

        with cache_file.open("r") as f:
            data = yaml.load(f.read(), Loader=yaml.Loader)

        self.assertIn(name, data)
        self.assertEqual(data[name], value)


class WhiskExampleConfTests(unittest.TestCase):
    def test_validate_example(self):
        p = subprocess.run(
            [ROOT / "bin" / "whisk", "validate", ROOT / "whisk.example.yaml"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        self.assertEqual(
            p.returncode, 0, "Validation failed with:\n%s" % p.stdout.decode("utf-8")
        )


class WhiskConfParseTests(WhiskTests, unittest.TestCase):
    def setUp(self):
        super().setUp()

        self.write_conf(
            """
            version: 2
            defaults:
                products:
                - test-dunfell
                mode: mode
                site: site

            versions:
                dunfell:
                    oeinit: {ROOT}/ci/dummy-init

            products:
                test-dunfell:
                    default_version: dunfell

            modes:
                mode: {{}}

            sites:
                site: {{}}

            """.format(
                ROOT=ROOT
            )
        )

    def test_project_root_expansion(self):
        temp_root = self.project_root / "temp_root"
        temp_root.mkdir()

        self.append_conf(
            """\
            project_root: temp_root
            hooks:
                pre_init: |
                    MY_PROJECT_ROOT=%{WHISK_PROJECT_ROOT}
            """
        )

        self.assertShellCode(
            """\
            . init-build-env
            """,
            {
                "WHISK_PROJECT_ROOT": str(temp_root.absolute()),
                "MY_PROJECT_ROOT": str(temp_root.absolute()),
            },
        )

    def test_env_var_expansion(self):
        self.append_conf(
            """\
            hooks:
                pre_init: |
                    MY_VAR=%{TEST_VAR}
            """
        )

        env = os.environ.copy()
        env["TEST_VAR"] = "FOOBAR"

        self.assertShellCode(
            """\
            . init-build-env
            """,
            {
                "MY_VAR": "FOOBAR",
            },
            env=env,
        )

        # A missing variable causes a failure
        self.assertShellCode(
            """\
            . init-build-env
            """,
            success=False,
        )


class WhiskFetchTests(WhiskTests, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.write_conf(
            """\
            version: 2
            defaults:
                mode: mode
                site: site

            fetch:
              commands:
                - echo main > %{{WHISK_PROJECT_ROOT}}/fetch

            versions:
                dunfell:
                    oeinit: {ROOT}/ci/dummy-init
                    fetch:
                      commands:
                        - echo dunfell >> %{{WHISK_PROJECT_ROOT}}/fetch

                    layers:
                      - name: core
                        fetch:
                            commands:
                            - echo core >> %{{WHISK_PROJECT_ROOT}}/fetch
                      - name: A
                        fetch:
                            commands:
                            - echo A >> %{{WHISK_PROJECT_ROOT}}/fetch
                      - name: test-environment
                        fetch:
                            commands:
                            - pwd >> %{{WHISK_PROJECT_ROOT}}/fetch
                            - echo ${{WHISK_PROJECT_ROOT}} >> %{{WHISK_PROJECT_ROOT}}/fetch
                            - echo ${{FOO}} >> %{{WHISK_PROJECT_ROOT}}/fetch

                zeus:
                    oeinit: {ROOT}/ci/dummy-init
                    fetch:
                      commands:
                        - echo zeus >> %{{WHISK_PROJECT_ROOT}}/fetch

                    layers:
                      - name: core
                        fetch:
                            commands:
                            - echo core >> %{{WHISK_PROJECT_ROOT}}/fetch
                      - name: A
                        fetch:
                            commands:
                            - echo A >> %{{WHISK_PROJECT_ROOT}}/fetch

            modes:
                mode: {{}}

            sites:
                site: {{}}

            """.format(
                ROOT=ROOT
            )
        )

    def assertFetches(self, code, fetches, **kwargs):
        self.assertShellCode(code, **kwargs)

        with (self.project_root / "fetch").open("r") as f:
            lines = [l.rstrip() for l in f.readlines()]

        self.assertEqual(lines, fetches)

    def test_fetch(self):
        self.append_conf(
            """\
            products:
                test-dunfell:
                    default_version: dunfell

                test-dunfell-core:
                    default_version: dunfell
                    layers:
                      - core

                test-dunfell-A:
                    default_version: dunfell
                    layers:
                      - A

                test-dunfell-core-A:
                    default_version: dunfell
                    layers:
                      - A
                      - core

                test-zeus:
                    default_version: zeus

                test-zeus-core:
                    default_version: zeus
                    layers:
                      - core

                test-zeus-A:
                    default_version: zeus
                    layers:
                      - A

                test-zeus-core-A:
                    default_version: zeus
                    layers:
                      - A
                      - core
            """
        )

        for v in ("dunfell", "zeus"):
            with self.subTest(v):
                self.assertFetches(
                    """\
                    . init-build-env --product=test-%s --fetch
                    """
                    % v,
                    ["main", v],
                )

            for l in (("core",), ("A",), ("core", "A")):
                name = "%s-%s" % (v, "-".join(l))
                with self.subTest(name):
                    self.assertFetches(
                        """\
                        . init-build-env --product=test-%s --fetch
                        """
                        % name,
                        ["main", v] + list(l),
                    )

    def test_fetch_env(self):
        self.append_conf(
            """\
            products:
                test-environment:
                    default_version: dunfell
                    layers:
                      - test-environment
            """
        )

        env = os.environ.copy()
        env["FOO"] = "BAR"

        self.assertFetches(
            """
            . init-build-env --product=test-environment --fetch
            """,
            [
                "main",
                "dunfell",
                str(self.project_root),
                str(self.project_root),
                "BAR",
            ],
            env=env,
        )


class WhiskVersionTests(WhiskTests, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.write_conf(
            """\
            version: 2
            defaults:
                mode: mode
                site: site

            versions:
                dunfell:
                    oeinit: {ROOT}/ci/dummy-init
                zeus:
                    oeinit: {ROOT}/ci/dummy-init

            products:
                test-dunfell:
                    default_version: dunfell
                test-dunfell2:
                    default_version: dunfell
                test-zeus:
                    default_version: zeus

            modes:
                mode: {{}}

            sites:
                site: {{}}

            """.format(
                ROOT=ROOT
            )
        )

    def test_default_version(self):
        self.assertShellCode(
            """\
            . init-build-env --product=test-dunfell --version=default
            """,
            {
                "WHISK_VERSION": "default",
                "WHISK_ACTUAL_VERSION": "dunfell",
            },
        )

        self.assertShellCode(
            """\
            . init-build-env --product=test-dunfell
            """,
            {
                "WHISK_VERSION": "default",
                "WHISK_ACTUAL_VERSION": "dunfell",
            },
        )

        self.assertShellCode(
            """\
            . init-build-env --product=test-zeus --version=default
            """,
            {
                "WHISK_VERSION": "default",
                "WHISK_ACTUAL_VERSION": "zeus",
            },
        )

        self.assertShellCode(
            """\
            . init-build-env --product=test-zeus
            """,
            {
                "WHISK_VERSION": "default",
                "WHISK_ACTUAL_VERSION": "zeus",
            },
        )

    def test_explicit_version(self):
        self.assertShellCode(
            """\
            . init-build-env --product=test-dunfell --version=zeus
            """,
            {
                "WHISK_VERSION": "zeus",
                "WHISK_ACTUAL_VERSION": "zeus",
            },
        )

        self.assertShellCode(
            """\
            . init-build-env --product=test-dunfell --product=test-zeus --version=zeus
            """,
            {
                "WHISK_VERSION": "zeus",
                "WHISK_ACTUAL_VERSION": "zeus",
            },
        )

    def test_mixed_product_implicit_default(self):
        """
        Mixing products with different versions using an implicit default
        should fail
        """
        self.assertShellCode(
            """\
            . init-build-env --product=test-dunfell --product=test-zeus
            """,
            success=False,
        )

    def test_mixed_product_explicit_default(self):
        """
        Different version products with explicit default should fail
        """
        self.assertShellCode(
            """\
            . init-build-env --product=test-dunfell --product=test-zeus --version=default
            """,
            success=False,
        )

    def test_changing_compatible_version_when_default(self):
        # Changing to a product with the same version after configuring
        self.assertShellCode(
            """\
            . init-build-env --product=test-dunfell --version=default
            configure --product=test-dunfell2
            """,
            {
                "WHISK_PRODUCTS": "test-dunfell2",
                "WHISK_VERSION": "default",
                "WHISK_ACTUAL_VERSION": "dunfell",
            },
        )

    def test_changing_incompatible_version_when_default(self):
        # Changing to a product with a different version after configuring with
        # default should fail
        self.assertShellCode(
            """\
            . init-build-env --product=test-dunfell --version=default
            configure --product=test-zeus
            """,
            success=False,
        )
        self.assertConfigVar("version", "default")

    def test_changing_incompatible_version_with_explicit_version(self):
        # Changing to a product with explicit version
        self.assertShellCode(
            """\
            . init-build-env --product=test-dunfell --version=dunfell
            configure --product=test-zeus
            """,
            {
                "WHISK_VERSION": "dunfell",
                "WHISK_ACTUAL_VERSION": "dunfell",
            },
        )

    def test_default_presists(self):
        # Default value persists between shell instances
        config_vars = {
            "WHISK_VERSION": "default",
            "WHISK_ACTUAL_VERSION": "dunfell",
            "WHISK_PRODUCTS": "test-dunfell",
        }
        self.assertShellCode(
            """\
            . init-build-env --product=test-dunfell --version=default
            """,
            config_vars,
        )
        self.assertShellCode(
            """\
            . init-build-env
            """,
            config_vars,
        )

    def test_explicit_version_persists(self):
        config_vars = {
            "WHISK_VERSION": "zeus",
            "WHISK_ACTUAL_VERSION": "zeus",
            "WHISK_PRODUCTS": "test-dunfell",
        }
        self.assertShellCode(
            """\
            . init-build-env --product=test-dunfell --version=zeus
            """,
            config_vars,
        )
        self.assertShellCode(
            """\
            . init-build-env
            """,
            config_vars,
        )

    def test_default_persists_across_versions(self):
        """
        Tests that when the default version persists, it means whatever version
        is supported by the configured products
        """
        self.assertShellCode(
            """\
            . init-build-env --product=test-dunfell --version=default
            """,
            {
                "WHISK_VERSION": "default",
                "WHISK_ACTUAL_VERSION": "dunfell",
                "WHISK_PRODUCTS": "test-dunfell",
            },
        )
        self.assertShellCode(
            """\
            . init-build-env --product=test-zeus
            """,
            {
                "WHISK_VERSION": "default",
                "WHISK_ACTUAL_VERSION": "zeus",
                "WHISK_PRODUCTS": "test-zeus",
            },
        )

    def test_changing_saved_explicit_with_default(self):
        # Test that the version is allowed to be changed to default after it
        # was explicitly set to a version not compatible with the new default
        self.assertShellCode(
            """\
            . init-build-env --product=test-dunfell --version=dunfell
            """,
            {
                "WHISK_VERSION": "dunfell",
                "WHISK_ACTUAL_VERSION": "dunfell",
                "WHISK_PRODUCTS": "test-dunfell",
            },
        )
        self.assertShellCode(
            """\
            . init-build-env --product=test-zeus --version=default
            """,
            {
                "WHISK_VERSION": "default",
                "WHISK_ACTUAL_VERSION": "zeus",
                "WHISK_PRODUCTS": "test-zeus",
            },
        )

    def test_keeping_explicit_verison(self):
        # Tests that if an explicit version is set, it is preserved even when
        # switching to a product that would be incompatible by default
        self.assertShellCode(
            """\
            . init-build-env --product=test-dunfell --version=dunfell
            """,
            {
                "WHISK_VERSION": "dunfell",
                "WHISK_ACTUAL_VERSION": "dunfell",
            },
        )
        self.assertShellCode(
            """\
            . init-build-env --product=test-zeus
            configure | grep "dunfell"
            """,
            {
                "WHISK_VERSION": "dunfell",
                "WHISK_ACTUAL_VERSION": "dunfell",
            },
        )


class WhiskInitTests(WhiskTests, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.write_conf(
            """\
            version: 2

            versions:
                dunfell:
                    oeinit: {ROOT}/ci/dummy-init
                zeus:
                    oeinit: {ROOT}/ci/dummy-init

            products:
                test-dunfell:
                    default_version: dunfell
                test-zeus:
                    default_version: zeus

            modes:
                modeA: {{}}
                modeB: {{}}

            sites:
                siteA: {{}}
                siteB: {{}}

            """.format(
                ROOT=ROOT
            )
        )

    def test_required_mode(self):
        self.assertShellCode(
            """\
            . init-build-env --product=test-dunfell --site=siteA
            """,
            success=False,
        )

    def test_required_site(self):
        self.assertShellCode(
            """\
            . init-build-env --product=test-dunfell --mode=modeA
            """,
            success=False,
        )

    def test_required_product(self):
        self.assertShellCode(
            """\
            . init-build-env --site=siteA --mode=modeA
            """,
            success=False,
        )

    def test_multiple_products_joined(self):
        self.assertShellCode(
            """\
            . init-build-env --products="test-dunfell test-zeus" --version=dunfell --mode=modeA --site=siteA
            """,
            {
                "WHISK_PRODUCTS": "test-dunfell test-zeus",
            },
        )

    def test_multiple_products_split(self):
        self.assertShellCode(
            """\
            . init-build-env --product=test-dunfell --product=test-zeus --version=dunfell --mode=modeA --site=siteA
            """,
            {
                "WHISK_PRODUCTS": "test-dunfell test-zeus",
            },
        )

    def test_defaults(self):
        self.append_conf(
            """\
            defaults:
                mode: modeA
                site: siteA
                products:
                - test-dunfell
            """
        )

        self.assertShellCode(
            """\
            . init-build-env
            """,
            {
                "WHISK_SITE": "siteA",
                "WHISK_MODE": "modeA",
                "WHISK_PRODUCTS": "test-dunfell",
            },
        )

        # Test defaults can be overridden
        self.assertShellCode(
            """\
            . init-build-env --mode=modeB --site=siteB --product=test-zeus
            """,
            {
                "WHISK_SITE": "siteB",
                "WHISK_MODE": "modeB",
                "WHISK_PRODUCTS": "test-zeus",
            },
        )

        # Test overrides are remembered in a subsequent environment initialization
        self.assertShellCode(
            """\
            . init-build-env
            """,
            {
                "WHISK_SITE": "siteB",
                "WHISK_MODE": "modeB",
                "WHISK_PRODUCTS": "test-zeus",
            },
        )

    def test_ignore_cache(self):
        self.append_conf(
            """\
            defaults:
                mode: modeA
                site: siteA
                products:
                - test-dunfell
            """
        )

        self.assertShellCode(
            """\
            . init-build-env --mode=modeB --site=siteB --product=test-zeus
            """,
            {
                "WHISK_SITE": "siteB",
                "WHISK_MODE": "modeB",
                "WHISK_PRODUCTS": "test-zeus",
            },
        )

        # --no-config causes the cache to be ignored
        self.assertShellCode(
            """\
            . init-build-env --no-config
            """,
            {
                "WHISK_SITE": "siteA",
                "WHISK_MODE": "modeA",
                "WHISK_PRODUCTS": "test-dunfell",
            },
        )

        # Cache wasn't overwritten by --no-config and continues to have the
        # originally configured values
        self.assertShellCode(
            """\
            . init-build-env
            """,
            {
                "WHISK_SITE": "siteB",
                "WHISK_MODE": "modeB",
                "WHISK_PRODUCTS": "test-zeus",
            },
        )


if __name__ == "__main__":
    unittest.main()
