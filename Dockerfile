# Use the official Python 3.10.9 slim-buster image
FROM python:3.10.9-slim-buster

# Update the package list and upgrade all packages
RUN apt update && apt upgrade -y

# Install git
RUN apt install git -y

# Copy the requirements file into the container
COPY requirements.txt /requirements.txt

# Upgrade pip and install the required Python packages
RUN pip3 install -U pip && pip3 install -U -r /requirements.txt

# Create a directory for the application
RUN mkdir /yahe2

# Set the working directory
WORKDIR /yahe2

# Copy the start script into the container
COPY start.sh /start.sh

# Expose the necessary port (e.g., 8000, adjust as needed)
# This fixes the issue by making the port available to Docker
EXPOSE 8080

# Set the default command to run the start script
CMD ["/bin/bash", "/start.sh"]
