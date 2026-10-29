FROM python:3.12-slim
WORKDIR /app
RUN groupadd --gid 10001 classroom && useradd --uid 10001 --gid classroom --no-create-home classroom && mkdir /data && chown classroom:classroom /data
COPY --chown=classroom:classroom server.py index.html app.js studio.js style.css warm-theme.css dice-lab.html lesson-plan.md lesson-video.json ./
COPY --chown=classroom:classroom vendor ./vendor
ENV HOST=0.0.0.0 PORT=8080 CLASSROOM_DATA_DIR=/data
USER classroom
EXPOSE 8080
CMD ["python3", "server.py"]
