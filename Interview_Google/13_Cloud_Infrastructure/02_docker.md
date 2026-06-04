# Docker — Containers From First Principles

## What Is It? (Plain English)

Imagine you have built a Python machine learning application that works perfectly on your laptop. You run it on a colleague's machine and it crashes with "package not found" errors. You deploy it to a cloud server and it fails because the server has Python 3.8 while you developed on Python 3.11. This is the classic "works on my machine" problem, and Docker solves it entirely.

Docker packages your application together with everything it needs to run — the Python version, every library, every configuration file, every environment variable — into a single, self-contained unit called a **container**. You can ship that container to any machine that runs Docker, and it will behave identically. The environment is bundled with the code. Think of a container as a shipping container in global trade: the contents are sealed inside, and it doesn't matter whether the ship is sailing from Shanghai or Los Angeles — the container opens the same way at every port.

A container is not a virtual machine (VM). A VM emulates an entire physical computer including the operating system kernel, which takes gigabytes of RAM and minutes to start. A container shares the host machine's Linux kernel and only packages the application code and its user-space dependencies. Containers start in milliseconds, use tens of megabytes, and you can run hundreds of them on a single server. For AI/ML specifically, Docker solves the reproducibility crisis: a training run that worked six months ago can be re-run identically by anyone on the team just by using the same Docker image.

## How It Works

You define a container using a **Dockerfile** — a plain text recipe that lists every step needed to build the environment. Docker reads this file and builds an **image** — a read-only, layered snapshot of the filesystem. Each instruction in the Dockerfile creates a new **layer**. Docker caches layers, so if you only change your application code (the last layer), Docker reuses all the earlier layers (OS packages, Python dependencies) from cache, making rebuilds fast.

When you run an image, Docker creates a **container** — a running instance with a thin writable layer on top of the read-only image. You can run dozens of containers from the same image simultaneously. The image is immutable; containers are ephemeral.

```ascii
DOCKERFILE                    IMAGE (layers)              CONTAINER (running)
─────────────                ──────────────────          ──────────────────────
FROM python:3.11         →   Layer 1: python:3.11        ┌────────────────────┐
RUN apt-get install ...  →   Layer 2: system packages    │ Writable layer     │ ← your writes
COPY requirements.txt .  →   Layer 3: requirements.txt   ├────────────────────┤
RUN pip install -r ...   →   Layer 4: pip packages       │ Layer 5: app code  │ (read-only)
COPY . /app              →   Layer 5: application code   │ Layer 4: pip pkgs  │ (read-only)
CMD ["uvicorn", "main"]  →   (startup command)           │ Layer 3: req.txt   │ (read-only)
                                                          │ Layer 2: sys pkgs  │ (read-only)
                                                          │ Layer 1: python    │ (read-only)
                                                          └────────────────────┘

IMAGE (immutable, shareable)  ──► CONTAINER INSTANCE 1 (port 8080)
                              ──► CONTAINER INSTANCE 2 (port 8081)
                              ──► CONTAINER INSTANCE 3 (port 8082)
```

**Multi-stage builds** are an advanced pattern that produces small final images. You use a large "builder" stage to compile code and install build tools, then copy only the compiled artefacts into a minimal "runtime" stage. This is critical for ML: your training image might be 10 GB (with CUDA, PyTorch, Jupyter), but your inference API image can be under 1 GB by only including the model weights and inference dependencies.

A **Docker registry** (Docker Hub, AWS ECR, Google Artifact Registry) stores and distributes images. You push an image to the registry with a version tag; Kubernetes (or any other machine) pulls it from there.

## Why Google Cares About This

Google deploys software in containers at a scale no other company matches. Every service in Google Cloud runs in a container. For AI/ML roles, Docker is the fundamental packaging mechanism for model training jobs, inference servers, and ML pipelines. Understanding Docker demonstrates that you can bridge the gap between data science (writing the code) and production engineering (making that code reproducible, deployable, and scalable). Google will expect you to know not just how to write a Dockerfile, but why certain patterns (multi-stage builds, non-root users, layer ordering) matter for security and performance.

## Interview Questions & Answers

### Q1: What is the difference between a Docker image and a Docker container? And what is a Docker registry?

**Answer:** This is the foundational question and many candidates conflate image and container. An **image** is a static, read-only, immutable blueprint — a layered filesystem snapshot. It is like a template or a class definition in object-oriented programming. An image has no runtime state; it just sits in storage. You can have an image and never run it.

A **container** is a live, running instance created from an image. It is like an object instantiated from a class. When Docker starts a container, it adds a thin writable layer on top of the image's read-only layers. The container has its own isolated process tree, network namespace, and filesystem view. When you write a file inside the container, that write goes to the writable layer only — the underlying image is never modified. When the container is deleted, the writable layer is destroyed. This means containers are stateful only during their lifetime; any data you want to persist must be written to a **volume** (a directory mounted from the host or a managed storage system).

A **Docker registry** is a server that stores and distributes images. Docker Hub is the public registry. AWS ECR (Elastic Container Registry), Google Artifact Registry, and Azure ACR are private, managed registries hosted by cloud providers. The workflow is: you `docker build` an image locally, `docker tag` it with a registry path (e.g., `us-docker.pkg.dev/myproject/models/inference:v1.2`), `docker push` it to the registry, and then any machine (including Kubernetes nodes) can `docker pull` that exact image and run it. Version tags on images (`v1.2`, `latest`, `commit-abc123`) are how you manage releases.

### Q2: Explain Docker's layer caching and how you should order instructions in a Dockerfile for best performance.

**Answer:** Every instruction in a Dockerfile (`FROM`, `RUN`, `COPY`, `ENV`) creates an immutable layer. Docker stores each layer with a hash. When you rebuild an image, Docker checks each layer from top to bottom. If the instruction and all the files it depends on are identical to a previous build, Docker reuses the cached layer instantly. The moment any layer changes, Docker invalidates that layer and all layers below it and rebuilds from that point.

This has a critical implication for how you order instructions. If you put `COPY . /app` early in the Dockerfile (before installing dependencies), then every time you change a single line of code, Docker invalidates the COPY layer and re-runs the expensive `pip install` step below it. This can turn a 1-second rebuild into a 5-minute rebuild.

The correct pattern is to order instructions from least-frequently-changing to most-frequently-changing. First, install OS-level packages (changes rarely). Then copy only the `requirements.txt` file and run `pip install` (this layer only rebuilds when dependencies change). Last, copy your application code (changes with every commit, but now only invalidates the cheap "copy files" layer). Here is the correct ordering:

```
FROM python:3.11-slim             # base image — changes rarely
RUN apt-get install -y libpq-dev  # system deps — changes rarely
COPY requirements.txt .            # only copy the deps file first
RUN pip install -r requirements.txt # install deps — only re-runs if requirements.txt changed
COPY . /app                        # copy app code LAST — rebuilds fast
CMD ["uvicorn", "api.main:app"]
```

For ML workflows, this matters enormously. A PyTorch installation can take 10 minutes. By separating the requirements file copy from the source code copy, you only re-install PyTorch when `requirements.txt` changes — which might happen once a month. Daily code changes rebuild in under 10 seconds.

### Q3: What is a multi-stage Docker build and when would you use it for an ML system?

**Answer:** A multi-stage build uses multiple `FROM` instructions in one Dockerfile. Each `FROM` starts a fresh stage with its own filesystem. You can copy specific files from one stage to another using `COPY --from=stage-name`. The final image only contains the last stage's filesystem — everything in earlier stages is discarded. This produces dramatically smaller images.

Consider the problem of building a C++ extension for Python (such as certain numerical libraries). The build requires a C compiler, header files, and build tools — but the compiled `.so` file is all you need at runtime. Without multi-stage builds, your final image contains the entire build toolchain (hundreds of MB). With multi-stage builds, the builder stage compiles everything, and the runtime stage copies only the compiled binary.

For ML systems, a concrete example: your model training pipeline needs PyTorch (large, with CUDA), Jupyter (for experimentation), and several development tools. Your inference API only needs the trained model weights, FastAPI, and a small subset of PyTorch for inference. A multi-stage build creates a `trainer` stage with the full environment and a `serving` stage that starts from a smaller base and only installs inference dependencies. The serving image might be 800 MB vs 8 GB for the training image — this matters for Kubernetes pull times, cold start latency, and registry storage costs.

Security is another motivation. Build stages often require network access, credentials (to pull private model weights from S3), or elevated privileges for compilation. Multi-stage builds ensure none of those credentials or build tools end up in the final image that runs in production.

### Q4: How does Docker networking work, and how do containers communicate with each other?

**Answer:** By default, Docker creates a private virtual network on the host machine. Each container gets an IP address on this internal network. Containers on the same Docker network can reach each other by container name (Docker provides automatic DNS resolution within a network). Containers are isolated from the host network and from containers on different networks unless you explicitly connect them.

When you run `docker run -p 8080:80 my-api`, you are publishing port 80 inside the container to port 8080 on the host machine. External traffic hits the host on port 8080 and Docker forwards it to port 80 inside the container. The container itself doesn't know it's being accessed via port 8080; it just listens on port 80.

For multi-container applications, **Docker Compose** lets you define multiple services (e.g., `api`, `database`, `redis`) in a single `docker-compose.yml` file. Compose automatically creates a shared network for all services and lets them reference each other by service name. For example, the API container can connect to `postgres:5432` and Docker resolves "postgres" to the PostgreSQL container's IP.

In the ORCA inventory system described in this repository, `docker-compose.yml` runs both the FastAPI backend and the Streamlit dashboard. The Streamlit container sends HTTP requests to `http://api:8080` (using the service name "api" as the hostname) and Docker routes those requests to the FastAPI container. This works because both containers are on the same Compose-created network. This is how microservices architectures work in development; in production (Kubernetes), the same concept applies via Kubernetes Services and DNS.

### Q5: What are Docker security best practices that matter in a production ML system?

**Answer:** The first and most important practice is **never running containers as root**. By default, Docker containers run as root inside the container. If a vulnerability in your application allows code execution, the attacker has root access to the container — which in certain misconfigurations can escape to the host. Add `USER nonroot` (or a specific numeric UID) at the end of your Dockerfile to drop privileges before running the application.

The second practice is **minimising the image surface area**. Use slim base images (`python:3.11-slim` instead of `python:3.11`, or `distroless` images) that omit shells, package managers, and debugging tools. An attacker who gets into a container with no bash shell and no package manager has very limited capabilities. For ML inference containers, there is no reason to include compilers, test frameworks, or development libraries.

Third, **never bake secrets into images**. It is tempting to `COPY .env /app/.env` in your Dockerfile, but that bakes your API keys into the image layer permanently — even if you delete the file in a later layer, it remains in the layer history and is visible with `docker history`. Secrets should be passed at container runtime via environment variables (`docker run -e GROQ_API_KEY=...`) or mounted as Kubernetes Secrets volumes.

Fourth, **pin your base image to a specific digest** (e.g., `FROM python:3.11.9-slim@sha256:abc123...`). Using `FROM python:latest` means your image rebuild next month might pull a different base and break. For ML systems where reproducibility of the training environment is critical (for auditability and debugging), pinning ensures the exact same base image is used for every build.

Fifth, **scan images for vulnerabilities** using tools like Trivy or Snyk in your CI/CD pipeline. Libraries like requests, cryptography, and PyYAML regularly publish security patches. An automated scan catches these before deployment.

## Key Points to Say in the Interview

- A container shares the host OS kernel — far lighter than a VM (starts in milliseconds, not minutes)
- Image layers are cached; wrong layer order causes expensive unnecessary rebuilds
- Multi-stage builds keep production images small and secrets-free
- Never run production containers as root — drop privileges with USER directive
- Docker Compose is for local multi-service development; Kubernetes is for production
- Secrets must be injected at runtime, never baked into image layers
- Pin base image versions for reproducibility — critical for ML experiment auditability
- Container images are immutable; containers are ephemeral — persist data with volumes

## Common Mistakes to Avoid

- Do not say "Docker and Kubernetes are the same thing" — Docker creates the image, Kubernetes runs and orchestrates containers at scale
- Do not say "COPY . /app before pip install is fine" — this kills layer cache and makes every rebuild slow
- Do not recommend running containers as root in production — this is a well-known security anti-pattern
- Do not forget that container filesystems are ephemeral — any ML model or database that needs to survive container restarts must use a volume
- Do not claim that containers provide full isolation like VMs — containers share the host kernel, which creates different (though manageable) security boundaries

## Further Reading

- [Docker Official Documentation](https://docs.docker.com/) — Start with "Get Started" then "Dockerfile best practices"
- [Docker Best Practices for Python](https://docs.docker.com/language/python/) — Official guide specific to Python applications
- [Google Distroless Images](https://github.com/GoogleContainerTools/distroless) — Minimal, secure base images for production containers
- [Multi-stage builds documentation](https://docs.docker.com/build/building/multi-stage/) — Official reference for multi-stage build patterns
- [Trivy — Container Vulnerability Scanner](https://trivy.dev/latest/docs/) — The standard open-source tool for scanning Docker images
