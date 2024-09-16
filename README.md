

```
virtualenv venv --python=python3.9
source venv/bin/activate
docker run -d --name redis-server -p 6379:6379 redis

```




启动celery
```
celery -A tasks worker --beat --loglevel=INFO --logfile=./log/celery.log
```


清除celery任务队列
```
celery -A tasks purge
```

