from setuptools import setup, find_packages

setup(
    name='pretix-signature-field',
    version='1.0.0',
    description='Adds a handwritten signature question type to the pretix checkout process',
    long_description=open('README.rst').read() if __import__('os').path.exists('README.rst') else '',
    url='https://github.com/plombier-services/pretix-signature-field',
    author='Plombier Services',
    author_email='dev@plombier-services.fr',
    license='Apache Software License',
    install_requires=['pretix'],
    packages=find_packages(exclude=['tests', 'tests.*']),
    include_package_data=True,
    package_data={
        'pretix_signature_field': [
            'static/pretix_signature_field/*.js',
            'static/pretix_signature_field/*.css',
            'templates/pretix_signature_field/*.html',
            'locale/*/LC_MESSAGES/*.po',
            'locale/*/LC_MESSAGES/*.mo',
        ]
    },
    entry_points={
        'pretix.plugin': [
            'pretix_signature_field=pretix_signature_field.apps:SignatureFieldApp',
        ],
    },
    python_requires='>=3.9',
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Topic :: Internet :: WWW/HTTP',
    ],
)
