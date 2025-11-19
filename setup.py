from setuptools import setup,find_packages

setup(
    name='ExperienceBuffers',
    version='0.1.0',
    packages=find_packages(where='experiencebuffers'),
    package_dir={'': 'experiencebuffers'},
    install_requires=[
        'opencv-python',
        'cv2-enumerate-cameras',
        'numpy',
        'pyaudio',
        'psutil',
        'pytz'
    ],
    entry_points={
        'console_scripts': [
            'ExperienceBuffers=core.BufferServer:main'
        ],
    },
    author='Lamar Gardere',
    description='ExperienceBuffers Buffer Server and buffer 0devices',
    python_requires='>=3.7',
)
