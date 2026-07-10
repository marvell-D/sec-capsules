# Self-Hosted GitHub Actions Runner

This repository is prepared for CI on a Linux self-hosted runner.

The workflow is located at:

```text
.github/workflows/ci.yml
```

It uses:

```yaml
runs-on: [self-hosted, linux]
```

## Tencent Server Target

Current intended development path:

```text
/home/ubuntu/git/sec-capsules
```

## Registration Steps

GitHub runner registration requires a repository-specific token from:

```text
GitHub repository -> Settings -> Actions -> Runners -> New self-hosted runner
```

On the Tencent server, the setup will generally look like:

```bash
mkdir -p ~/actions-runner/sec-capsules
cd ~/actions-runner/sec-capsules

curl -o actions-runner-linux-x64.tar.gz -L <github-runner-download-url>
tar xzf actions-runner-linux-x64.tar.gz

./config.sh \
  --url https://github.com/<owner>/<repo> \
  --token <runner-registration-token> \
  --labels linux,self-hosted,sec-capsules \
  --unattended

sudo ./svc.sh install
sudo ./svc.sh start
```

Do not commit runner tokens or generated runner credentials.

