
__version__ = '0.1.dev'

from setuptools import setup, find_packages

with open('README.md', 'r') as fh:
	long_description = fh.read()

setup(
	name='longs-python-toolbox',
	version=__version__,
	author='Xiaolong "Bruce" Liu',
	author_email='liuxiaolong125@gmail.com',
	description='A python tool colletion for personal use.',
	long_description=long_description,
	long_description_content_type='text/markdown',
	url='https://github.com/longavailable/python-toolbox',
	packages=find_packages(),
	classifiers=[
		'Programming Language :: Python :: 3',
		'License :: OSI Approved :: MIT License',
		'Operating System :: OS Independent',
	],
	python_requires='>=3.6',
	install_requires=[
		'adaptive-curvefitting',
		'copyheaders',
		'earthengine-api',
		'geopandas',
		'shapely',
		'google-cloud-storage',
		'matplotlib',
		'numpy',
		'pandas',
		'PyGithub',
		'python-magic',
		'requests-toolbelt',
		'scipy',
		'voronoi-diagram-for-polygons',
	 ],
)