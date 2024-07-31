from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models.signals import post_save

class User(AbstractUser):
  username = models.CharField(unique=True, max_length=100)
  email = models.EmailField(unique=True, max_length=255)
  full_name = models.CharField(max_length=100)
  otp = models.CharField(max_length=100, null=True, blank=True)
  refresh_token = models.CharField(max_length=1000, null=True, blank=True)

  USERNAME_FIELD = 'email'
  REQUIRED_FIELDS = ['username']

  def __str__(self):
    return self.email
  
  def save(self, *args, **kwargs):
    email_username, full_name = self.email.split("@")
    if self.full_name == "" or self.full_name == None:
      self.full_name = email_username
    if self.username == "" or self.username == None:
      self.username = email_username
    super(User, self).save(*args, **kwargs)

class Profile(models.Model):
  user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
  image = models.FileField(upload_to="user_folder", default="default-user.jpg", null=True, blank=True)
  full_name = models.CharField(max_length=100)
  country = models.CharField(max_length=100, null=True, blank=True)
  about = models.TextField(null=True, blank=True)
  created_at = models.DateTimeField(auto_now_add=True)

  def __str__(self):
    if self.full_name:
      return str(self.full_name)
    else: 
      return str(self.user.full_name)
  
  def save(self, *args, **kwargs):
    if self.full_name == "" or self.full_name == None:
      self.full_name = self.user.full_name
    super(Profile, self).save(*args, **kwargs)

def create_user_profile(sender, instance, created, **kwargs):
  if created:
    Profile.objects.create(user=instance)

def save_user_profile(sender, instance, **kwargs):
  instance.profile.save()

post_save.connect(create_user_profile, sender=User)
post_save.connect(save_user_profile, sender=User)
  

