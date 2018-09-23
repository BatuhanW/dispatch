from setuptools import setup, find_packages

setup(name='dispatch',
    version='1.0.0',
    description='A publishing platform for modern newspapers',
    url='https://github.com/ubyssey/dispatch',
    author='Peter Siemens',
    author_email='peterjsiemens@gmail.com',
    license='GPL',
    packages=find_packages(),
    scripts=['dispatch/bin/dispatch-admin'],
    include_package_data=True,
    install_requires=[
        'django == 2.1.0',
        'djangorestframework == 3.7.7',
        'pillow',
        'requests',
        'jsonfield',
    ],
    extras_require={
        'dev': [
            'coverage'
        ]
    },
    zip_safe=False)
