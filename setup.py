from setuptools import setup, find_packages

setup(
    name="computer_use_demo",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pyautogui",
        "anthropic",
        "websockets>=12.0",
        "numpy",
        "pyaudio"
    ]
)
