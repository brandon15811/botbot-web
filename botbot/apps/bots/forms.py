import base64
import re
import uuid

from django import forms

from botbot.apps.accounts import models as accounts_models
from . import models

server_regex = re.compile(r"^[\w\-\.]*\:\d*$")

class ChannelForm(forms.ModelForm):
    identifiable_url = forms.BooleanField(
        required=False, initial=True, help_text="Identifiable URLs may leak "
            "channel information as part of the referrer details if when URL "
            "is clicked from the logs")

    class Meta:
        model = models.Channel
        fields = ('chatbot', 'name', 'password', 'is_public', 'is_active')

    def save(self, *args, **kwargs):
        """
        If it's an identifiable url, set the slug to ``None``.

        If it's not an identifiable url, set the slug to a random value if it
        is not already set.
        """
        if self.cleaned_data['identifiable_url']:
            self.instance.slug = None
        elif not self.instance.slug:
            channels = models.Channel.objects.all()
            while not self.instance.slug or\
                    channels.filter(slug=self.instance.slug).exists():
                self.instance.slug = base64.b32encode(uuid.uuid4().bytes)[:4]\
                    .lower()
        return super(ChannelForm, self).save(*args, **kwargs)

class ChannelRequestForm(forms.Form):
    channel_name = forms.CharField()
    server = forms.CharField(label="IRC Server")
    github = forms.URLField(label="GitHub Repo URL",
        help_text="If the channel supports a github repo, the url to the repo.",
        required=False)

    name = forms.CharField(label="Your name")
    email = forms.EmailField(label="Your e-mail")
    nick = forms.CharField(label="Your IRC Nick")
    op = forms.BooleanField(label="Are you a channel op?")

    def clean_channel_name(self):
        channel_name = self.cleaned_data['channel_name']
        if models.Channel.objects.filter(name=channel_name).exists():
            raise forms.ValidationError("Sorry, this channel is already being monitored.")

        return channel_name

    def clean_server(self):
        server = self.cleaned_data['server']
        if not server_regex.match(server):
            raise forms.ValidationError("Incorrect format, should be <url>:<port>")
        return server


class UsersForm(forms.Form):
    users = forms.ModelMultipleChoiceField(required=False,
        queryset=accounts_models.User.objects.all())

    def __init__(self, channel, *args, **kwargs):
        super(UsersForm, self).__init__(*args, **kwargs)
        self.channel = channel
        if channel:
            self.fields['users'].initial = [p.pk for p in channel.users.all()]

    def save(self):
        users = self.cleaned_data['users']
        self.channel.membership_set.exclude(user__in=users).delete()
        for user in users:
            self.channel.membership_set.get_or_create(user=user)
