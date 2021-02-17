[![Build Status](https://github.com/garmin/whisk/workflows/build/badge.svg?branch=master&event=push)](https://github.com/garmin/whisk/actions?query=workflow%3Abuild+event%3Apush+branch%3Amaster)

# Whisk
<img src="./images/whisk.svg" width="250" height="250">

Organize OpenEmbedded products

## What is Whisk?

Whisk is a tool for managing complex product configurations when using
OpenEmbedded and the Yocto project. The key features are:
1. **Single source tree** Whisk is designed to allow multiple products with
   vastly different configurations to co-exist in the same repository (and the
   same branch)
2. **Multiple axes of configuration** You can configure what you want to build
   (products), how you want to build them (modes) and where you are build them
   (sites)
3. **Multiple products builds** Whisk sets up each product in it's own
   [multiconfig][]. This means that you can configure and build multiple
   products with the same invocation of bitbake, and that each products has
   its own isolated bitbake environment.
4. **Isolated layer configuration** Each product may define which layers it
   needs to build. If multiple products are configured and the set of layers
   required for each product is not equal, Whisk will use [BBMASK][] to mask
   off the unused layers independently for each product. See [Product Layer Masking][]
5. **Multiple versions** Whisk lets you define multiple different versions of
   layers to target for your product. Each product can define a default version
   to use if unspecified, but users can override the default. This allows
   several use cases, such as testing products with more recent Yocto releases,
   or maintaining similar builds across multiple Yocto versions for testing.

[Requirements]: #requirements
## Requirements

Whisk is primarily written in Python, with a small initialization shell script
to setup the build environment. The Python code runs under
[Pipenv](https://pypi.org/project/pipenv/) and the initialization script will
use it to automatically install the required dependencies. See the Pipenv
documentation for installation instructions.

[Using Whisk]: #using-whisk
## Using Whisk

_NOTE: This is the end users guide to using Whisk. If you are looking for
instructions on how to setup and configure Whisk for your project, see
[Project Setup][]_

Building a product inside a repo using Whisk is a fairly straight forward
process. Whisk itself lets you configure 4 attributes about what you want to
build:
1. **The product** This is the actual thing you want to build. You may choose
   to build one or more products in a given environment
2. **The mode** This allows you to choose how you want to build the product(s).
   For example, there may be a mode to build the product(s) for internal use,
   and a mode to build the product(s) for external (public) consumption.
3. **The site** This is where you are building from. There may be build options
   that are affected by your physical location, such as mirror setups, use of
   distributed compilers, etc.
4. **The version** This defines what version of Yocto you want to build the
   product(s) against. Allowing this to be defined as a build parameter allows
   quickly testing if a product is compatible with multiple versions of Yocto
   and having different products use different versions independently of each
   other. If you don't really care about this, you may specify the version
   as `default` to choose the default version defined for the product(s)

### Initializing the environment

To get started, you must first initialize the environment by sourcing the
initialization script, usually located in your project root. When you
initialize, you may specify any of the above items to be configured. If you do
not specify one, the default specified in the projects `whisk.yaml` file will
be used (if no default is specified there, you will be forced to provide a
value). If you would like a list of options that can be specified when
initializing the environment, use the `--help` option, like so:

    . init-build-env --help

If you would like a complete list of options that may be specified for
`--products`, `--mode`, `--site`, or `--version`, use the `--list` option:

    . init-build-env --list

Once you have decided what options you would like to use, initialize your build
environment, e.g.

    . init-build-env --product=foo --mode=debug --site=here --version=default

This will setup the build environment and change your working directory to the
build directory

*Note:* If you choose `default` for the version and specify multiple products
to be configured, whisk will fail if all specified products do not use the same
version.

### Reconfiguring

At any time after the environment has been initialized, you may change certain
configuration options such as what product, mode, or site you are using without
re-initializing the environment. To do this, run the `configure` command
defined by whisk. This command takes all of the same arguments as the
`init-build-env` script, so for example

    configure --list

Will show all the possible options for products, modes, sites, and versions.

*Note:* While most things can be changed when reconfiguring, there are some
options that whisk can't change without re-initializing the environment, such
as the version and build directory.

### Building

After configuring the build environment, you should have all of the normal
bitbake tools at your disposal to build products. The simplest thing to do is
to run the command:

    bitbake all-targets

This will build all of the default targets for all of the currently selected
products.

If you want to build a specific recipe for a specific product, be aware that
whisk puts each product into it's own [multiconfig][]. So, if you want to build
`core-image-minimal` for product `foo`, you would need to run:

    bitbake mc:product-foo:core-image-minimal

Likewise, to dump the base environment for product `foo`, you would run:

    bitbake -e mc:product-foo

### Build output

Whisk splits each build into its own build directory to ensure that they do not
interfere with each other. By default, each build has [TMPDIR][] set to
`${TOPDIR}/tmp/${WHISK_MODE}/${WHISK_ACTUAL_VERSION}/${WHISK_PRODUCT}` (see
[Build Variables][]).

In addition, each build also has [DEPLOY_DIR][] set to
`${TOPDIR}/deploy/${WHISK_MODE}/${WHISK_ACUTAL_VERSION}/${WHISK_PRODUCT}`

[Project Setup]: #project-setup
## Project Setup

A typical project would integrate Whisk with the following steps:
1. Add Whisk to the project. We recommend pulling it in as a git submodule, but
   you may use whatever module composition tool you like (or even just copy the
   source)
2. Link the whisk [init-build-env script](./init-build-env) into the project
   root, for example with the command:

    ln -s whisk/init-build-env ./init-build-env

3. Write a `whisk.yaml` file in the project root along side the
   `init-build-env` symlink. See [Project Configuration][]

[Project Configuration]: #project-configuration
## Project Configuration

The project is primarily configured through the `whisk.yaml` file, usually
located in the project root. Extensive documentation on the options and their
values is available in the [example configuration][].

To help validate your configuration, Whisk includes a `validate` command that
can be run on your whisk.yaml file to validate it is correctly formatted.

[Building in a Container]: #building-in-a-container
## Building in a Container

Whisk supports building your products inside a
[Pyrex](https://github.com/garmin/pyrex) container as a first-class option. To
enable this support, generate a Pyrex configuration file and add the `pyrex` section
to your versions as shown in the [example configuration][]. When this is
enabled, Whisk will automatically setup the correct environment variables to
use pyrex when invoking your build commands.

[Build Variables]: #build-variables
## Build Variables

Whisk sets a number of bitbake variables that can be used in recipes to make
they aware of the current user configuration. These are:

| Variable | Description |
|----------|-------------|
| `WHISK_PROJECT_ROOT` | The absolute path the to the project root |
| `WHISK_PRODUCT` | The current product. When evaluated in a products multiconfig, it will be the name of the product. In the base environment, it will be `"core"` |
| `WHISK_PRODUCTS` | The list of products the user has currently selected to be built |
| `WHISK_MODE` | The name of the mode the user has currently selected |
| `WHISK_SITE` | The name of the site the user has currently selected |
| `WHISK_VERSION` | The name of the version the user has currently selected. May be `"default"` if the user specified that |
| `WHISK_ACTUAL_VERSION` | the name of the version the user has specified, resolved to an actual name (e.g. will never be `"default"` |
| `WHISK_TARGETS` | The combined set of all default build targets for all user configured products |

In addition, some variables are set for each defined product. In this table
`${product}` will be replaced with the actual name of the product:

| Variable | Description |
|----------|-------------|
| `WHISK_TARGET_${product}` | The default targets for this product |
| `WHISK_DEPLOY_DIR_${product}` | The [DEPLOY_DIR][] for this product (see [Sharing Files Between Products][]) |
| `DEPLOY_DIR_${product}` | *Deprecated* Alias for `WHISK_DEPLOY_DIR_${product}`, only available when config file version is `1`. New products should not use this variable as it can cause problems with overrides. |

Finally, some variables are also set in the shell environment when the hook
scripts are run. These include `WHISK_PROJECT_ROOT`, `WHISK_PRODUCTS`,
`WHISK_MODE`, `WHISK_SITE`, `WHISK_VERSION`, `WHISK_ACTUAL_VERSION`, and the
variables in the following tables:

| Variable | Description |
|----------|-------------|
| `WHISK_BUILD_DIR` | The absolute path to the user-specified build directory |
| `WHISK_INIT` | This will have the value `"true"` if the hook is being invoked during the first initialization of the environment, and `"false"` during a reconfigure |


[Sharing Files Between Products]: #sharing-files-between-products
## Sharing Files Between Products

A common need that arises when building with [multiconfig][] is how to share
files between different multiconfigs (or the base environment). The easiest
answer to that a multiconfig that wants to share something with another
multiconfig should [deploy][] the files it wants to share from a given recipe.
Then, another multiconfig can [mcdepends][] on that source recipes `do_deploy`
task and pull the files out of the source multiconfigs [DEPLOY_DIR][]. However,
in order for this to work, the `DEPLOY_DIR` of each source multiconfig must be
at a known location. To aid in this discovery, Whisk creates a
`WHISK_DEPLOY_DIR` variable for each defined product, so that all products can
easily reference each others deployed files.

For example, assume we have two products, `source` and `dest`. `source` has a
recipe called "hello.bb" that contains:

    inherit deploy

    do_deploy {
        echo "Hello" > ${DEPLOYDIR}/hello.txt
    }
    addtask do_deploy before do_build

`dest` wants to bring in this file in another recipe, so it does:

    do_install() {
        cp ${WHISK_DEPLOY_DIR_source}/hello.txt ${D}/hello_source.txt
    }
    do_install[mcdepends] = "mc:source:dest:hello:do_deploy"


Note that for this to work properly, the `source` product would have to have
been configured by the user, which Whisk doesn't check.

*As of this writing, it's not possible to query another multiconfigs variables,
although it's been discussed. This would eliminate the need for publishing the
per-product `WHISK_DEPLOY_DIR` variables, because one could simply query what
`DEPLOY_DIR` is set to in the source multiconfig*

[Product Layer Masking]: #product-layer-masking
## Product Layer Masking

Product layer masking requires Yocto 3.2 (gatesgarth) or later, as this is the
first version to support separate [BBMASK][] per multiconfig.

[Layer Fetching]: #layer-fetching
## Layer Fetching

Whisk has the ability to automatically fetch the layers required to build a
given set of products when configuring. This a user to fetch only the required
subset, instead of being forced to checkout all layers. This can significantly
cut down on the amount of fetching, particularly since whisk encourages the
same remote module to be present in the source tree multiple times for multiple
versions (e.g. you will probably have oe-core or poky present multiple times in
your source tree; one for each version). This can be particularly help for CI
builds where the extra fetching wastes computation time.

Fetching is controlled by `fetch` objects in the `whisk.yaml` file. The top
level, version objects, and layer sets can all have a fetch object, see the
[example configuration][] for more information.

A detailed example for using fetch commands with `git submodules` will now be
explained. Other methods of fetching can be used, but whisk fetching pairs
particularly well with submodules.

The example will focus on an example repository with a `.gitmodules` file that
looks like this:

```
[submodule "whisk"]
    path = whisk
    branch = master
    url = https://github.com/garmin/whisk.git
[submodule "yocto-3.0/zeus"]
    path = yocto-3.0/poky
    branch = zeus
    url = https://git.yoctoproject.org/git/poky
[submodule "yocto-3.0/meta-mingw"]
    path = yocto-3.1/meta-mingw
    branch = zeus
    url = https://git.yoctoproject.org/git/meta-mingw
[submodule "yocto-3.1/poky"]
    path = yocto-3.1/poky
    branch = dunfell
    url = https://git.yoctoproject.org/git/poky
[submodule "yocto-3.1/meta-mingw"]
    path = yocto-3.1/meta-mingw
    branch = dunfell
    url = https://git.yoctoproject.org/git/meta-mingw
```

And a `whisk.yaml` file that looks like this:

```yaml
version: 1

defaults:
  mode: default
  site: default

versions:
  dunfell:
    description: Yocto 3.1
    oeinit: "%{WHISK_PROJECT_ROOT}/yocto-3.1/poky/oe-init-build-env"

    layers:
    - name: core
      paths:
      - "%{WHISK_PROJECT_ROOT}/yocto-3.1/poky/meta"
      fetch:
        commands:
        - git submodule update --init yocto-3.1/poky

    - name: mingw
      paths:
      - "%{WHISK_PROJECT_ROOT}/yocto-3.1/meta-mingw"
      fetch:
        commands:
        - git submodule update --init yocto-3.1/meta-mingw

  zeus:
    description: Yocto 3.0
    oeinit: "%{WHISK_PROJECT_ROOT}/yocto-3.0/poky/oe-init-build-env"

    layers:
    - name: core
      paths:
      - "%{WHISK_PROJECT_ROOT}/yocto-3.0/poky/meta"
      fetch:
        commands:
        - git submodule update --init yocto-3.0/poky

    - name: mingw
      paths:
      - "%{WHISK_PROJECT_ROOT}/yocto-3.0/meta-mingw"
      fetch:
        commands:
        - git submodule update --init yocto-3.0/meta-mingw

modes:
  default:
  desription: Default mode

sites:
  default:
  description: Default site

core:
  layers:
    - core

  conf: |
    MACHINE ?= "qemux86-64"
    DISTRO ?= "poky"

products:
  albatross:
    default_verison: dunfell
    layers:
    - core

  typhoon:
    default_version: dunfell
    layers:
    - core
    - mingw

  phoenix:
    default_version: zeus
    layers:
    - core

  eagle:
    default_version: zeus
    layers:
    - core
    - mingw
```

Now, when a product is configured with the `--fetch` argument, whisk will
automatically run `git submodule update --init <LAYER>` for layers the product
requires, but users who want all layers can still easily fetch everything with
a simple `git submodule update --init` command. If you wanted to ensure that
your CI jobs only fetch the minimum number of required layers, you might use a
script like this:

```shell
#! /bin/sh
set -e

# First fetch whisk
git submodule update --init whisk

# Configure whisk, instructing it to fetch the required product layers
. init-build-env -n --product=$PRODUCT --fetch

# Build default targets
bitbake all-targets
```

[multiconfig]: https://www.yoctoproject.org/docs/3.1/bitbake-user-manual/bitbake-user-manual.html#executing-a-multiple-configuration-build
[BBMASK]: https://www.yoctoproject.org/docs/3.1/bitbake-user-manual/bitbake-user-manual.html#var-bb-BBMASK
[TMPDIR]: https://www.yoctoproject.org/docs/3.1/mega-manual/mega-manual.html#var-TMPDIR
[DEPLOY_DIR]: https://www.yoctoproject.org/docs/3.1/mega-manual/mega-manual.html#var-DEPLOY_DIR
[example configuration]: ./whisk.example.yaml
[deploy]: https://www.yoctoproject.org/docs/3.1/mega-manual/mega-manual.html#ref-classes-deploy
[mcdepends]: https://www.yoctoproject.org/docs/3.1/mega-manual/mega-manual.html#bb-enabling-multiple-configuration-build-dependencies
