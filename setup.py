from distutils.core import setup

setup(
    name='lendingclub',
    version=open('lendingclub/VERSION').read().strip(),
    author='Jeremy Gillick',
    author_email='none@none.com',
    packages=['lendingclub', 'lendingclub.tests'],
    package_data={
        'lendingclub': ['VERSION', 'filter.handlebars'],
        'lendingclub.tests': ['assets/*.*']
    },
    url='http://github.com/jgillick/LendingClub',
    license=open('LICENSE.txt').read(),
    description='An library for Lending Club that lets you check your cash balance, search for notes, build orders and invest.',
    long_description=open('README.rst').read(),
    install_requires=[
        "requests >= 1.2.3",
        "beautifulsoup4 >= 4.1.3",
        "html5lib >= 0.95",
        "pybars >= 0.0.4"
    ],
    platforms='osx, posix, linux, windows',
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: POSIX',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Environment :: Console',
        'Topic :: Office/Business :: Financial',
        'Topic :: Utilities'
    ],
    keywords='lendingclub investing api lending club'
)
