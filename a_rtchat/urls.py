from django.urls import path
from .views import *

urlpatterns = [
    path('',chat_view,name="home"),
    path('chat/public/toggle/', toggle_public_chat_view, name="toggle-public-chat"),
    path('chat/<username>',get_or_create_chatroom,name="start-chat"),
    path('chat/fileupload/<chatroom_name>', chat_file_upload_view, name="chat-file-upload"),
    path('<chatroom_name>',chat_view,name='chatroom'),
    path('message/<pk>/edit/', message_edit_view, name="message-edit"),
    path('message/<pk>/delete/', message_delete_view, name="message-delete"),
    
]
