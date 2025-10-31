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
# Just like build-alias, but skips the recipe in the event that the
# product is not configured

inherit build-alias

PRODUCT ?= ""
CURRENT_PRODUCT ?= ""

python() {
    product = d.getVar('PRODUCT')
    if product and product != d.getVar('WHISK_CONF_PRODUCT'):
        raise bb.parse.SkipRecipe('Product %s not configured' % product)

    current_product= d.getVar('CURRENT_PRODUCT')
    if current_product and current_product != d.getVar('WHISK_CURRENT_PRODUCT'):
        raise bb.parse.SkipRecipe('Current product is not %s' % current_product)

    if not product and not current_product:
        raise bb.parse.SkipRecipe('PRODUCT and CURRENT_PRODUCT not defined')
}
