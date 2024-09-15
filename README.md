

```
virtualenv venv --python=python3.9
source venv/bin/activate
docker run -d --name redis-server -p 6379:6379 redis

```