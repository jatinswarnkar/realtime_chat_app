import json
from channels.generic.websocket import WebsocketConsumer
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from .models import *
from asgiref.sync import async_to_sync

class ChatroomConsumer(WebsocketConsumer):
    def connect(self):
        self.user = self.scope['user']
        self.chatroom_name = self.scope['url_route']['kwargs']['chatroom_name']
        self.chatroom = get_object_or_404(ChatGroup,group_name=self.chatroom_name)
        
        async_to_sync(self.channel_layer.group_add)(
            self.chatroom_name , self.channel_name
        )
        
        # add and update online users
        if self.user not in self.chatroom.users_online.all():
            self.chatroom.users_online.add(self.user)
            self.update_online_count()
        
        self.accept()
        
    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)(
            self.chatroom_name , self.channel_name
        )
        
        # remove and update online users
        if self.user in self.chatroom.users_online.all():
            self.chatroom.users_online.remove(self.user)
            self.update_online_count()
    
    def receive(self,text_data):
        text_data_json = json.loads(text_data)
        body = text_data_json.get('body', '')
        code_body = text_data_json.get('code_body', '')
        
        if code_body and code_body.strip():
            lang = text_data_json.get('code_language', '')
            code_markdown = f"```{lang}\n{code_body}\n```"
            body = f"{body}\n\n{code_markdown}" if body.strip() else code_markdown
            
        if not body.strip():
            return
            
        
        is_whisper = False
        if body.startswith('/whisper '):
            is_whisper = True
            body = body.replace('/whisper ', '', 1)
            
        import re
        
        def render_code_block(match):
            lang = match.group(1) or "plain text"
            code = match.group(2)
            html = f'''<!-- CODE_BLOCK_START -->
<div class="w-full bg-[#1e1e2e] border border-[#2e2e3e] rounded-xl overflow-hidden my-2 text-left code-block-wrapper text-gray-300">
    <div class="flex justify-between items-center bg-[#252538] px-3 py-2 border-b border-[#2e2e3e]">
        <div class="flex items-center gap-2 text-gray-400">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
            </svg>
            <span class="text-xs font-semibold uppercase tracking-wider">{lang}</span>
        </div>
        <button x-data="{{ copied: false }}" @click="navigator.clipboard.writeText($el.closest('.code-block-wrapper').querySelector('code').innerText); copied = true; setTimeout(() => copied = false, 2000)" class="text-gray-400 hover:text-white transition-colors bg-transparent border-0 p-1 cursor-pointer" title="Copy Code">
            <svg x-show="!copied" xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
            <svg x-show="copied" x-cloak xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
            </svg>
        </button>
    </div>
    <div class="bg-[#1e1e2e] w-full overflow-x-auto">
        <pre class="!m-0 !bg-transparent"><code class="language-{match.group(1) or ''} !bg-transparent p-4 text-sm font-mono">{code}</code></pre>
    </div>
</div>
<!-- CODE_BLOCK_END -->'''
            return html.strip()
            
        body = re.sub(r'```(\w+)?\n?(.*?)```', render_code_block, body, flags=re.DOTALL)
        
        message = GroupMessage.objects.create(
            body = body.strip() if body else "",
            author = self.user,
            group = self.chatroom,
            is_whisper = is_whisper
        )
        
        event = {
            'type': 'message_handler',
            'message_id': message.id,
        }
        
        async_to_sync(self.channel_layer.group_send)(
            self.chatroom_name , event
        )
        
    def message_handler(self,event):
        message_id = event['message_id']
        message = GroupMessage.objects.get(id=message_id)
        context = {
            'message': message,
            'user': self.user,
        }
        html = render_to_string("partials/chat_message_p.html",context = context)
        self.send(text_data=html)
        
    def update_online_count(self):
        online_count = self.chatroom.users_online.count()
        
        event = {
            'type':'online_count_handler',
            'online_count': online_count
        }
        async_to_sync(self.channel_layer.group_send)(self.chatroom_name,event)
    
    def online_count_handler(self,event):
        online_count = event['online_count']
        html = render_to_string('partials/online_count.html',{'online_count':online_count})
        self.send(text_data=html)
        
    def message_delete_handler(self, event):
        message_id = event['message_id']
        html = f'<li id="msg-{message_id}" hx-swap-oob="delete"></li>'
        self.send(text_data=html)
        
    def message_edit_handler(self, event):
        message_id = event['message_id']
        message = GroupMessage.objects.get(id=message_id)
        context = {
            'message': message,
            'user': self.user,
            'is_oob_edit': True
        }
        html = render_to_string("chat_message.html", context=context)
        self.send(text_data=html)

class WhiteboardConsumer(WebsocketConsumer):
    def connect(self):
        self.user = self.scope['user']
        self.chatroom_name = self.scope['url_route']['kwargs']['chatroom_name']
        async_to_sync(self.channel_layer.group_add)(
            f"wb_{self.chatroom_name}", self.channel_name
        )
        self.accept()

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)(
            f"wb_{self.chatroom_name}", self.channel_name
        )
        
    def receive(self, text_data):
        try:
            data = json.loads(text_data)
            if hasattr(self.user, 'profile'):
                data['username'] = self.user.profile.name
                data['avatar'] = self.user.profile.avatar
            else:
                data['username'] = self.user.username
                data['avatar'] = '/static/images/avatar.svg'
            data['userId'] = self.user.id
            text_data = json.dumps(data)
        except Exception:
            pass

        async_to_sync(self.channel_layer.group_send)(
            f"wb_{self.chatroom_name}",
            {
                'type': 'draw_handler',
                'data': text_data
            }
        )
        
    def draw_handler(self, event):
        self.send(text_data=event['data'])