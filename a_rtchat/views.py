from django.http import Http404
from django.shortcuts import get_object_or_404, render,redirect
from django.contrib.auth.decorators import login_required
from .models import *
from .forms import *
from django.http import Http404, HttpResponse
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

@login_required 
def chat_view(request, chatroom_name='public-chat'):
    chat_group = get_object_or_404(ChatGroup, group_name=chatroom_name)
    chat_messages = chat_group.chat_messages.all()[:30]
    form = ChatmessageCreateForm()
    
    other_user = None
    
    if chat_group.is_private:
        if request.user not in chat_group.members.all():
            raise Http404()
        for member in chat_group.members.all():
            if member != request.user:
                other_user = member
                break
    
    if request.htmx:   #.method == 'POST' withour htmx
        form = ChatmessageCreateForm(request.POST)
        if form.is_valid:
            message = form.save(commit=False)
            message.author = request.user
            message.group = chat_group
            message.save()
            context = {
                'message': message,
                'user': request.user
            }
            return render(request,'partials/chat_message_p.html',context)
    
    context = {
        'chat_messages': chat_messages,
        'form': form,
        'other_user': other_user,
        'chatroom_name': chatroom_name,
    }
    
    return render(request,'chat.html',context)



def get_or_create_chatroom(request,username):
    if request.user.username == username:
        return redirect('home')
    
    other_user = User.objects.get(username = username)
    my_chatrooms = request.user.chat_groups.filter(is_private=True)
    
    if my_chatrooms.exists():
        for chatroom in my_chatrooms:
            if other_user in chatroom.members.all():
                return redirect('chatroom', chatroom.group_name)
   
    chatroom = ChatGroup.objects.create( is_private = True )
    chatroom.members.add(other_user, request.user)   
    return redirect('chatroom', chatroom.group_name)


@login_required
def message_delete_view(request, pk):
    message = get_object_or_404(GroupMessage, id=pk, author=request.user)
    if request.method == "POST":
        chatroom_name = message.group.group_name
        message_id = message.id
        message.delete()
        
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            chatroom_name,
            {
                'type': 'message_delete_handler',
                'message_id': message_id
            }
        )
        return HttpResponse("")

@login_required
def message_edit_view(request, pk):
    message = get_object_or_404(GroupMessage, id=pk, author=request.user)
    
    if request.method == "POST":
        new_body = request.POST.get("body")
        if new_body:
            is_whisper = False
            if new_body.startswith('/whisper '):
                is_whisper = True
                new_body = new_body.replace('/whisper ', '', 1)
                
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
                
            parsed_body = re.sub(r'```(\w+)?\n?(.*?)```', render_code_block, new_body, flags=re.DOTALL)
            
            message.body = parsed_body
            message.is_whisper = is_whisper
            message.save()
            
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                message.group.group_name,
                {
                    'type': 'message_edit_handler',
                    'message_id': message.id
                }
            )
            return HttpResponse("")
            
    raw_body = message.body
    import re
    pattern = r'<!-- CODE_BLOCK_START -->.*?<code class="language-(\w*)?[^>]*>(.*?)</code>.*?<!-- CODE_BLOCK_END -->'
    def repl(m):
        lang = m.group(1) or ""
        code = m.group(2)
        return f"```{lang}\n{code}\n```"
    raw_body = re.sub(pattern, repl, raw_body, flags=re.DOTALL)
    
    if message.is_whisper:
        raw_body = "/whisper " + raw_body
            
    return render(request, "partials/chat_message_edit.html", {"message": message, "raw_body": raw_body})

@login_required
def chat_file_upload_view(request, chatroom_name):
    chat_group = get_object_or_404(ChatGroup, group_name=chatroom_name)
    
    if request.method == 'POST':
        form = ChatmessageCreateForm(request.POST, request.FILES)
        if form.is_valid():
            message = form.save(commit=False)
            message.author = request.user
            message.group = chat_group
            
            body = form.cleaned_data.get('body', '') or ''
            code_body = request.POST.get('code_body', '')
            if code_body and code_body.strip():
                lang = request.POST.get('code_language', '')
                code_markdown = f"```{lang}\n{code_body}\n```"
                body = f"{body}\n\n{code_markdown}" if body.strip() else code_markdown

            if body.startswith('/whisper '):
                message.is_whisper = True
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
            message.body = body.strip() if body and body.strip() else ""
            
            message.save()
            
            # Broadcast the message via Channels
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                chatroom_name,
                {
                    'type': 'message_handler',
                    'message_id': message.id,
                }
            )
            # Return 204 No Content so HTMX doesn't swap anything (the WebSocket will render the message)
            return HttpResponse(status=204)
            
    return HttpResponse(status=400)