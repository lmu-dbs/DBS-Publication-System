FROM node:18-alpine

WORKDIR /app

# Copy package.json for dependency installation
COPY ./frontend/package.json ./

# Install dependencies
RUN npm install

# Install react-scripts globally for development
RUN npm install -g react-scripts

# Don't copy the code - we'll mount it as a volume instead

EXPOSE 3000

# Start the application in development mode with hot-reloading
CMD ["npm", "start"]
