#   Copyright (c) 2013-2015, University of Bern, Switzerland.
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

"""
Setuptools script
"""

from setuptools import setup

setup(name='mcn_icn_so',
      version='1.4',
      description='MCN ICN SO',
      author='Andre Gomes - University of Bern, Switzerland',
      author_email='gomes@inf.unibe.ch',
      url='http://www.iam.unibe.ch',
      license='Apache 2.0',
      packages=['wsgi', 'mcn_cc_sdk'],
)
