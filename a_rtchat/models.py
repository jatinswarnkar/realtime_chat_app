from django.db import models
from django.contrib.auth.models import User
import shortuuid

# Create your models here.
class ChatGroup(models.Model):
    group_name = models.CharField(max_length=128,unique=True,default=shortuuid.uuid)
    users_online = models.ManyToManyField(User,related_name='online_in_groups',blank = True)
    is_private = models.BooleanField(default=False)
    members = models.ManyToManyField(User,related_name='chat_groups',blank=True)
    
    def __str__(self):
        return self.group_name
    
class GroupMessage(models.Model):
    group = models.ForeignKey(ChatGroup,related_name='chat_messages',on_delete=models.CASCADE)
    author = models.ForeignKey(User,on_delete=models.CASCADE)
    body = models.CharField(max_length=300, blank=True, null=True)
    file = models.FileField(upload_to='chat_files/', blank=True, null=True)
    is_whisper = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f'{self.author.username} : {self.body}'
        
    @property
    def is_image(self):
        if self.file:
            ext = self.file.name.split('.')[-1].lower()
            return ext in ['jpg', 'jpeg', 'png', 'gif', 'svg', 'webp']
        return False
        
    @property
    def filename(self):
        if self.file:
            import os
            return os.path.basename(self.file.name)
        return ""
    
    class Meta:
        ordering = ['-created']