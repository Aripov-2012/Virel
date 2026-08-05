from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model, authenticate, login
from django.contrib.auth.views import LoginView
from django.contrib import messages
from django.db import IntegrityError
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User
from .models import Blog, Comment, Subscription, Profile, Conversation, Message, Tag, PostView, SavedPost, PhoneVerification
from .sms import send_sms
User = get_user_model()

class LoginWithStats(LoginView):
    template_name = "registration/login.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["user_count"] = User.objects.count()
        context["message_count"] = Message.objects.count()
        context["post_count"] = Blog.objects.count()
        return context


def home(request):
    user_count = User.objects.count()      # всего пользователей
    post_count = Blog.objects.count()      # всего постов
    comment_count = Comment.objects.count()  # всего комментариев

    context = {
        'user_count': user_count,
        'post_count': post_count,
        'comment_count': comment_count,
    }
    return render(request, 'home.html', context)


def register(request):
    if request.user.is_authenticated:
        return redirect('blog_page')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')

        if not username or not email or not password:
            messages.error(request, 'Имя пользователя, email и пароль обязательны.')
            return render(request, 'registration/register.html')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Пользователь с таким именем уже существует.')
            return render(request, 'registration/register.html')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'Пользователь с таким email уже существует.')
            return render(request, 'registration/register.html')

        try:
            User.objects.create_user(
                username=username,
                email=email,
                password=password,
            )
        except IntegrityError:
            messages.error(request, 'Не удалось создать аккаунт. Попробуйте другое имя пользователя.')
            return render(request, 'registration/register.html')

        messages.success(request, 'Аккаунт создан. Теперь вы можете войти.')
        return redirect('login')

    return render(request, 'registration/register.html')


def _format_phone(phone: str) -> str:
    """Нормализует номер телефона к формату +998XXXXXXXXX."""
    phone = phone.strip().replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    if phone.startswith('998') and len(phone) == 12:
        phone = '+' + phone
    elif phone.startswith('8') and len(phone) == 12:
        phone = '+998' + phone[1:]
    elif not phone.startswith('+'):
        phone = '+' + phone
    return phone


def register_phone(request):
    """Регистрация по номеру телефона с SMS-подтверждением."""
    if request.user.is_authenticated:
        return redirect('blog_page')

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'send_code':
            username = request.POST.get('username', '').strip()
            password = request.POST.get('password', '')
            phone = _format_phone(request.POST.get('phone', ''))

            if not username or not password or not phone:
                messages.error(request, 'Все поля обязательны.')
                return render(request, 'registration/register_phone.html')

            if len(password) < 6:
                messages.error(request, 'Пароль должен быть не менее 6 символов.')
                return render(request, 'registration/register_phone.html')

            if User.objects.filter(username=username).exists():
                messages.error(request, 'Пользователь с таким именем уже существует.')
                return render(request, 'registration/register_phone.html')

            if Profile.objects.filter(phone=phone).exists():
                messages.error(request, 'Этот номер телефона уже зарегистрирован.')
                return render(request, 'registration/register_phone.html')

            code = PhoneVerification.generate_code()
            PhoneVerification.objects.create(
                phone=phone,
                code=code,
                purpose='register',
                username=username,
                password=password,
            )

            send_sms(phone, f'Ваш код подтверждения Virel: {code}')

            return render(request, 'registration/register_phone.html', {
                'step': 'verify',
                'phone': phone,
                'username': username,
            })

        elif action == 'verify_code':
            phone = _format_phone(request.POST.get('phone', ''))
            code = request.POST.get('code', '').strip()
            username = request.POST.get('username', '').strip()

            verification = PhoneVerification.objects.filter(
                phone=phone,
                purpose='register',
                is_used=False,
            ).order_by('-created_at').first()

            if not verification:
                messages.error(request, 'Код не найден. Запросите новый.')
                return render(request, 'registration/register_phone.html', {
                    'step': 'verify',
                    'phone': phone,
                    'username': username,
                })

            if verification.is_expired():
                messages.error(request, 'Срок действия кода истёк. Запросите новый.')
                return render(request, 'registration/register_phone.html', {
                    'step': 'verify',
                    'phone': phone,
                    'username': username,
                    'expired': True,
                })

            verification.attempts += 1
            verification.save(update_fields=['attempts'])

            if verification.attempts > 5:
                verification.is_used = True
                verification.save(update_fields=['is_used'])
                messages.error(request, 'Слишком много попыток. Запросите новый код.')
                return render(request, 'registration/register_phone.html', {
                    'step': 'verify',
                    'phone': phone,
                    'username': username,
                    'expired': True,
                })

            if verification.code != code:
                messages.error(request, 'Неверный код. Попробуйте ещё раз.')
                return render(request, 'registration/register_phone.html', {
                    'step': 'verify',
                    'phone': phone,
                    'username': username,
                    'remaining_attempts': 5 - verification.attempts,
                })

            # Код верный — создаём аккаунт
            verification.is_used = True
            verification.save(update_fields=['is_used'])

            try:
                user = User.objects.create_user(
                    username=verification.username,
                    password=verification.password,
                )
                profile, _ = Profile.objects.get_or_create(user=user)
                profile.phone = phone
                profile.save(update_fields=['phone'])
            except IntegrityError:
                messages.error(request, 'Ошибка создания аккаунт. Попробуйте снова.')
                return redirect('register_phone')

            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, 'Аккаунт создан! Добро пожаловать!')
            return redirect('blog_page')

        elif action == 'resend_code':
            phone = _format_phone(request.POST.get('phone', ''))
            username = request.POST.get('username', '').strip()

            last_verification = PhoneVerification.objects.filter(
                phone=phone,
                purpose='register',
                is_used=False,
            ).order_by('-created_at').first()

            if last_verification and not last_verification.can_resend():
                messages.error(request, 'Повторная отправка возможна через 60 секунд.')
                return render(request, 'registration/register_phone.html', {
                    'step': 'verify',
                    'phone': phone,
                    'username': username,
                })

            code = PhoneVerification.generate_code()
            PhoneVerification.objects.create(
                phone=phone,
                code=code,
                purpose='register',
                username=username,
                password=last_verification.password if last_verification else '',
            )

            send_sms(phone, f'Ваш новый код подтверждения Virel: {code}')
            messages.success(request, 'Новый код отправлен!')

            return render(request, 'registration/register_phone.html', {
                'step': 'verify',
                'phone': phone,
                'username': username,
            })

    return render(request, 'registration/register_phone.html')


def login_phone(request):
    """Вход по номеру телефона с SMS-подтверждением."""
    if request.user.is_authenticated:
        return redirect('blog_page')

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'send_code':
            phone = _format_phone(request.POST.get('phone', ''))
            password = request.POST.get('password', '')

            if not phone or not password:
                messages.error(request, 'Введите номер телефона и пароль.')
                return render(request, 'registration/login_phone.html')

            profile = Profile.objects.filter(phone=phone).select_related('user').first()
            if not profile:
                messages.error(request, 'Аккаунт с таким номером телефона не найден.')
                return render(request, 'registration/login_phone.html')

            user = authenticate(request, username=profile.user.username, password=password)
            if not user:
                messages.error(request, 'Неверный пароль.')
                return render(request, 'registration/login_phone.html')

            code = PhoneVerification.generate_code()
            PhoneVerification.objects.create(
                phone=phone,
                code=code,
                purpose='login',
                username=profile.user.username,
            )

            send_sms(phone, f'Ваш код для входа в Virel: {code}')

            return render(request, 'registration/login_phone.html', {
                'step': 'verify',
                'phone': phone,
            })

        elif action == 'verify_code':
            phone = _format_phone(request.POST.get('phone', ''))
            code = request.POST.get('code', '').strip()

            verification = PhoneVerification.objects.filter(
                phone=phone,
                purpose='login',
                is_used=False,
            ).order_by('-created_at').first()

            if not verification:
                messages.error(request, 'Код не найден. Запросите новый.')
                return render(request, 'registration/login_phone.html', {
                    'step': 'verify',
                    'phone': phone,
                })

            if verification.is_expired():
                messages.error(request, 'Срок действия кода истёк. Запросите новый.')
                return render(request, 'registration/login_phone.html', {
                    'step': 'verify',
                    'phone': phone,
                    'expired': True,
                })

            verification.attempts += 1
            verification.save(update_fields=['attempts'])

            if verification.attempts > 5:
                verification.is_used = True
                verification.save(update_fields=['is_used'])
                messages.error(request, 'Слишком много попыток. Запросите новый код.')
                return render(request, 'registration/login_phone.html', {
                    'step': 'verify',
                    'phone': phone,
                    'expired': True,
                })

            if verification.code != code:
                messages.error(request, 'Неверный код. Попробуйте ещё раз.')
                return render(request, 'registration/login_phone.html', {
                    'step': 'verify',
                    'phone': phone,
                    'remaining_attempts': 5 - verification.attempts,
                })

            verification.is_used = True
            verification.save(update_fields=['is_used'])

            user = User.objects.filter(username=verification.username).first()
            if user:
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                messages.success(request, 'Добро пожаловать!')
                return redirect('blog_page')

            messages.error(request, 'Пользователь не найден.')
            return redirect('login_phone')

        elif action == 'resend_code':
            phone = _format_phone(request.POST.get('phone', ''))

            last_verification = PhoneVerification.objects.filter(
                phone=phone,
                purpose='login',
                is_used=False,
            ).order_by('-created_at').first()

            if last_verification and not last_verification.can_resend():
                messages.error(request, 'Повторная отправка возможна через 60 секунд.')
                return render(request, 'registration/login_phone.html', {
                    'step': 'verify',
                    'phone': phone,
                })

            profile = Profile.objects.filter(phone=phone).select_related('user').first()
            if not profile:
                messages.error(request, 'Аккаунт не найден.')
                return redirect('login_phone')

            code = PhoneVerification.generate_code()
            PhoneVerification.objects.create(
                phone=phone,
                code=code,
                purpose='login',
                username=profile.user.username,
            )

            send_sms(phone, f'Ваш новый код для входа в Virel: {code}')
            messages.success(request, 'Новый код отправлен!')

            return render(request, 'registration/login_phone.html', {
                'step': 'verify',
                'phone': phone,
            })

    return render(request, 'registration/login_phone.html')


def blog_page(request):
    search_query = request.GET.get('q', '').strip()
    sort = request.GET.get('sort', 'new').strip()

    posts = Blog.objects.select_related('author').prefetch_related(
        'likes',
        'comments__author',
        'comments__likes',
    )

    if search_query:
        posts = posts.filter(
            Q(title__icontains=search_query)
            | Q(content__icontains=search_query)
            | Q(author__username__icontains=search_query)
        )

    if sort == 'mine':
        if request.user.is_authenticated:
            posts = posts.filter(author=request.user)
        else:
            sort = 'new'

    if sort == 'popular':
        posts = posts.annotate(likes_count=Count('likes')).order_by('-likes_count', '-created_at')
    else:
        posts = posts.order_by('-created_at')

    following_ids = set()
    saved_post_ids = set()
    if request.user.is_authenticated:
        following_ids = set(
            Subscription.objects.filter(follower=request.user).values_list('following_id', flat=True)
        )
        saved_post_ids = set(
            SavedPost.objects.filter(user=request.user).values_list('post_id', flat=True)
        )

    return render(
        request,
        'blog.html',
        {
            'posts': posts,
            'search_query': search_query,
            'current_sort': sort,
            'following_ids': following_ids,
            'saved_post_ids': saved_post_ids,
        },
    )


@login_required
def admin_page(request):
    sort = request.GET.get('sort', 'new').strip()
    posts = Blog.objects.filter(author=request.user)
    if sort == 'popular':
        posts = posts.annotate(likes_count=Count('likes')).order_by('-likes_count', '-created_at')
    else:
        sort = 'new'
        posts = posts.order_by('-created_at')
    return render(request, 'admin.html', {'posts': posts, 'current_sort': sort})


@login_required
def create_post(request):
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        image = request.FILES.get('image')
        attachment = request.FILES.get('attachment')
        tags_str = request.POST.get('tags', '').strip()

        if title and content:
            post = Blog.objects.create(
                author=request.user,
                title=title,
                content=content,
                image=image,
                attachment=attachment,
            )
            if tags_str:
                _apply_tags(post, tags_str)
            return redirect('admin_page')

    return render(request, 'create_post.html')


@login_required
def update_post(request, id):
    post = get_object_or_404(Blog, id=id, author=request.user)

    if request.method == 'POST':
        post.title = request.POST.get('title', '').strip()
        post.content = request.POST.get('content', '').strip()

        new_image = request.FILES.get('image')
        remove_image = request.POST.get('remove_image') == '1'
        if new_image:
            if post.image:
                post.image.delete(save=False)
            post.image = new_image
        elif remove_image and post.image:
            post.image.delete(save=False)
            post.image = None

        new_attachment = request.FILES.get('attachment')
        remove_attachment = request.POST.get('remove_attachment') == '1'
        if new_attachment:
            if post.attachment:
                post.attachment.delete(save=False)
            post.attachment = new_attachment
        elif remove_attachment and post.attachment:
            post.attachment.delete(save=False)
            post.attachment = None

        post.save()

        tags_str = request.POST.get('tags', '').strip()
        _apply_tags(post, tags_str)

        return redirect('admin_page')

    return render(request, 'update_post.html', {'post': post})


@login_required
def delete_post(request, id):
    post = get_object_or_404(Blog, id=id, author=request.user)
    if request.method == 'POST':
        post.delete()
        return redirect('admin_page')
    return render(request, 'delete_post.html', {'post': post})


@login_required
def add_comment(request, id):
    post = get_object_or_404(Blog, id=id)
    if request.method == 'POST':
        text = request.POST.get('text', '').strip()
        if text:
            comment = Comment.objects.create(
                post=post,
                author=request.user,
                text=text,
            )
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse(
                    {
                        'ok': True,
                        'comment': {
                            'id': comment.id,
                            'author': comment.author.username,
                            'text': comment.text,
                            'created_at': timezone.localtime(comment.created_at).strftime('%Y-%m-%d %H:%M'),
                            'likes_count': comment.likes.count(),
                            'profile_url': reverse('profile_page', args=[comment.author.id]),
                            'like_url': reverse('toggle_comment_like', args=[comment.id]),
                        },
                    }
                )
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'ok': False, 'error': 'Комментарий не может быть пустым.'}, status=400)
    return redirect(request.META.get('HTTP_REFERER', 'blog_page'))


@login_required
def toggle_post_like(request, id):
    post = get_object_or_404(Blog, id=id)
    if request.method == 'POST':
        liked = post.likes.filter(id=request.user.id).exists()
        if liked:
            post.likes.remove(request.user)
            liked = False
        else:
            post.likes.add(request.user)
            liked = True
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'ok': True, 'liked': liked, 'likes_count': post.likes.count()})
    return redirect(request.META.get('HTTP_REFERER', 'blog_page'))


@login_required
def toggle_comment_like(request, id):
    comment = get_object_or_404(Comment, id=id)
    if request.method == 'POST':
        liked = comment.likes.filter(id=request.user.id).exists()
        if liked:
            comment.likes.remove(request.user)
            liked = False
        else:
            comment.likes.add(request.user)
            liked = True
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'ok': True, 'liked': liked, 'likes_count': comment.likes.count()})
    return redirect(request.META.get('HTTP_REFERER', 'blog_page'))


@login_required
def toggle_subscription(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    if request.method != 'POST':
        return redirect('blog_page')

    if target_user == request.user:
        messages.error(request, 'Нельзя подписаться на самого себя.')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'ok': False, 'error': 'Нельзя подписаться на самого себя.'}, status=400)
        return redirect(request.META.get('HTTP_REFERER', 'blog_page'))

    subscription = Subscription.objects.filter(follower=request.user, following=target_user)
    is_subscribed = False
    if subscription.exists():
        subscription.delete()
        is_subscribed = False
    else:
        Subscription.objects.create(follower=request.user, following=target_user)
        is_subscribed = True

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(
            {
                'ok': True,
                'is_subscribed': is_subscribed,
                'followers_count': Subscription.objects.filter(following=target_user).count(),
            }
        )

    return redirect(request.META.get('HTTP_REFERER', 'blog_page'))


@login_required
def subscriptions_feed(request):
    subscriptions = (
        Subscription.objects.filter(follower=request.user)
        .select_related('following')
        .order_by('following__username')
    )
    subscribed_users = [sub.following for sub in subscriptions]
    posts = (
        Blog.objects.filter(author__in=subscribed_users)
        .select_related('author')
        .prefetch_related('likes', 'comments__author', 'comments__likes')
        .order_by('-created_at')
    )

    return render(
        request,
        'subscriptions.html',
        {
            'subscribed_users': subscribed_users,
            'posts': posts,
        },
    )


def profile_page(request, user_id):
    profile_user = get_object_or_404(User, id=user_id)
    Profile.objects.get_or_create(user=profile_user)
    posts = (
        Blog.objects.filter(author=profile_user)
        .select_related('author')
        .prefetch_related('likes', 'comments__author', 'comments__likes')
        .order_by('-created_at')
    )
    followers_count = Subscription.objects.filter(following=profile_user).count()
    following_count = Subscription.objects.filter(follower=profile_user).count()
    is_following = False
    if request.user.is_authenticated and request.user != profile_user:
        is_following = Subscription.objects.filter(
            follower=request.user,
            following=profile_user,
        ).exists()

    return render(
        request,
        'profile.html',
        {
            'profile_user': profile_user,
            'posts': posts,
            'followers_count': followers_count,
            'following_count': following_count,
            'is_following': is_following,
        },
    )


@login_required
def edit_profile(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip().lower()
        bio = request.POST.get('bio', '').strip()
        reverse_mobile_messages = request.POST.get('reverse_mobile_messages') == '1'
        remove_avatar = request.POST.get('remove_avatar') == '1'
        new_avatar = request.FILES.get('avatar')

        if username and username != request.user.username:
            if User.objects.filter(username=username).exists():
                messages.error(request, 'Пользователь с таким именем уже существует.')
                return render(request, 'edit_profile.html', {'profile': profile})
            request.user.username = username
            request.user.save(update_fields=['username'])

        if email:
            request.user.email = email
            request.user.save(update_fields=['email'])

        if new_avatar:
            if profile.avatar:
                profile.avatar.delete(save=False)
            profile.avatar = new_avatar
        elif remove_avatar and profile.avatar:
            profile.avatar.delete(save=False)
            profile.avatar = None

        profile.bio = bio
        profile.reverse_mobile_messages = reverse_mobile_messages
        profile.save()
        messages.success(request, 'Профиль обновлён.')
        return redirect('profile_page', user_id=request.user.id)

    return render(request, 'edit_profile.html', {'profile': profile})


@login_required
def chat_list(request):
    conversations = (
        Conversation.objects.filter(participants=request.user)
        .prefetch_related('participants')
        .order_by('-updated_at')
    )

    chat_cards = []
    for conversation in conversations:
        others = [p for p in conversation.participants.all() if p.id != request.user.id]
        title = ", ".join([p.username for p in others]) or request.user.username
        last_message = (
            conversation.messages.select_related('sender')
            .order_by('-created_at')
            .first()
        )
        chat_cards.append(
            {
                'id': conversation.id,
                'title': title,
                'last_message': last_message,
            }
        )

    return render(
        request,
        'chat_list.html',
        {
            'chat_cards': chat_cards,
        },
    )


@login_required
def start_chat(request, user_id):
    other_user = get_object_or_404(User, id=user_id)
    if other_user == request.user:
        messages.error(request, 'Нельзя начать чат с самим собой.')
        return redirect('chat_list')

    conversation = (
        Conversation.objects.filter(participants=request.user)
        .filter(participants=other_user)
        .annotate(participants_count=Count('participants'))
        .filter(participants_count=2)
        .first()
    )

    if not conversation:
        conversation = Conversation.objects.create()
        conversation.participants.add(request.user, other_user)

    return redirect('chat_room', conversation_id=conversation.id)


@login_required
def chat_room(request, conversation_id):
    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        participants=request.user,
    )
    participants = list(conversation.participants.all())
    others = [p for p in participants if p.id != request.user.id]
    chat_title = ", ".join([p.username for p in others]) or request.user.username
    messages_list = conversation.messages.select_related('sender').all()
    return render(
        request,
        'chat_room.html',
        {
            'conversation': conversation,
            'messages': messages_list,
            'chat_title': chat_title,
        },
    )


def _apply_tags(post, tags_str):
    """Парсит строку тегов через запятую и привязывает к посту."""
    names = [t.strip() for t in tags_str.split(',') if t.strip()]
    tags = []
    for name in names:
        from .models import translit_slug
        slug = translit_slug(name)
        tag, _ = Tag.objects.get_or_create(slug=slug, defaults={'name': name})
        tags.append(tag)
    post.tags.set(tags)


@login_required
def for_you_feed(request):
    """Персонализированная лента на основе лайков и просмотров."""
    user = request.user

    # Теги из лайкнутых постов (вес 3)
    liked_tags = (
        Tag.objects.filter(posts__likes=user)
        .values_list('id', flat=True)
    )

    # Теги из просмотренных постов (вес 1)
    viewed_tags = (
        Tag.objects.filter(posts__views__user=user)
        .values_list('id', flat=True)
    )

    # Посты которые пользователь уже лайкал или смотрел
    seen_post_ids = set(
        Blog.objects.filter(likes=user).values_list('id', flat=True)
    ) | set(
        PostView.objects.filter(user=user).values_list('post_id', flat=True)
    )

    # Считаем score для каждого поста
    liked_tag_ids = set(liked_tags)
    viewed_tag_ids = set(viewed_tags)

    if not liked_tag_ids and not viewed_tag_ids:
        # Новый пользователь — показываем популярные
        posts = (
            Blog.objects.select_related('author')
            .prefetch_related('likes', 'comments__author', 'comments__likes', 'tags')
            .annotate(score=Count('likes'))
            .order_by('-score', '-created_at')[:50]
        )
    else:
        # Аннотируем score: +3 за каждый совпадающий тег из лайков, +1 из просмотров
        posts = (
            Blog.objects.select_related('author')
            .prefetch_related('likes', 'comments__author', 'comments__likes', 'tags')
            .exclude(id__in=seen_post_ids)
            .filter(tags__isnull=False)
            .distinct()
        )

        # Считаем score в Python (django ORM не может сложить разные M2M)
        scored = []
        for post in posts:
            post_tag_ids = set(post.tags.values_list('id', flat=True))
            score = len(post_tag_ids & liked_tag_ids) * 3 + len(post_tag_ids & viewed_tag_ids)
            if score > 0:
                scored.append((score, post))

        scored.sort(key=lambda x: (-x[0], -x[1].created_at.timestamp()))
        posts = [p for _, p in scored[:50]]

    following_ids = set()
    saved_post_ids = set()
    if request.user.is_authenticated:
        following_ids = set(
            Subscription.objects.filter(follower=request.user).values_list('following_id', flat=True)
        )
        saved_post_ids = set(
            SavedPost.objects.filter(user=request.user).values_list('post_id', flat=True)
        )

    return render(
        request,
        'for_you.html',
        {
            'posts': posts,
            'following_ids': following_ids,
            'saved_post_ids': saved_post_ids,
        },
    )


def posts_by_tag(request, slug):
    """Посты по конкретному тегу."""
    tag = get_object_or_404(Tag, slug=slug)
    posts = (
        Blog.objects.filter(tags=tag)
        .select_related('author')
        .prefetch_related('likes', 'comments__author', 'comments__likes', 'tags')
        .order_by('-created_at')
    )

    following_ids = set()
    saved_post_ids = set()
    if request.user.is_authenticated:
        following_ids = set(
            Subscription.objects.filter(follower=request.user).values_list('following_id', flat=True)
        )
        saved_post_ids = set(
            SavedPost.objects.filter(user=request.user).values_list('post_id', flat=True)
        )

    return render(
        request,
        'tag_posts.html',
        {
            'tag': tag,
            'posts': posts,
            'following_ids': following_ids,
            'saved_post_ids': saved_post_ids,
        },
    )


@login_required
def track_post_view(request, id):
    """Записывает просмотр поста пользователем."""
    if request.method == 'POST':
        post = get_object_or_404(Blog, id=id)
        PostView.objects.update_or_create(
            user=request.user,
            post=post,
        )
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'ok': True})
    return JsonResponse({'ok': False}, status=400)


@login_required
def toggle_save_post(request, id):
    post = get_object_or_404(Blog, id=id)
    if request.method == 'POST':
        saved = SavedPost.objects.filter(user=request.user, post=post)
        if saved.exists():
            saved.delete()
            is_saved = False
        else:
            SavedPost.objects.create(user=request.user, post=post)
            is_saved = True
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'ok': True, 'saved': is_saved})
    return redirect(request.META.get('HTTP_REFERER', 'blog_page'))


@login_required
def saved_posts_page(request):
    saved = (
        SavedPost.objects.filter(user=request.user)
        .select_related('post__author')
        .prefetch_related('post__likes', 'post__comments__author', 'post__comments__likes', 'post__tags')
    )
    posts = [s.post for s in saved]

    following_ids = set(
        Subscription.objects.filter(follower=request.user).values_list('following_id', flat=True)
    )

    return render(
        request,
        'saved_posts.html',
        {
            'posts': posts,
            'following_ids': following_ids,
        },
    )