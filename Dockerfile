FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend

ARG FRONTEND_BASE_URL=/
ARG VITE_API_BASE_URL
ARG VITE_BILIBILI_VIDEO_BVID
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend ./
ENV FRONTEND_BASE_URL=${FRONTEND_BASE_URL}
RUN FRONTEND_BASE_URL=${FRONTEND_BASE_URL} VITE_API_BASE_URL=${VITE_API_BASE_URL} VITE_BILIBILI_VIDEO_BVID=${VITE_BILIBILI_VIDEO_BVID} npm run build

# Use the existing socialsim-new-app image as base to reuse installed packages.
# Tag it first: docker tag socialsim-new-app fos-build-base
FROM fos-build-base AS backend

WORKDIR /app

COPY pyproject.toml README.md ./
COPY requirements.txt ./

COPY requirements-gaworld.txt ./

# Only install packages not already present in the base image
RUN pip install --no-cache-dir --default-timeout=1000 -r requirements.txt || true \
    && pip install --no-cache-dir lxml-html-clean || true \
    && pip install --no-cache-dir --default-timeout=1000 -r requirements-gaworld.txt || true

COPY src ./src
COPY scripts ./scripts

# Install the application code (--no-deps is safe here because we installed requirements above)
RUN pip install --no-cache-dir --no-deps .

RUN rm -rf ./frontend/dist
COPY --from=frontend-build /app/frontend/dist ./frontend/dist
COPY docker/backend-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV FOS_FRONTEND_DIST_PATH=/app/frontend/dist

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
