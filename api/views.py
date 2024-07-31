import random
from django.shortcuts import render, redirect
from api import serializer as api_serializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework import generics
from userauths.models import User, Profile
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response
from rest_framework import status
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from api import models as api_model
from decimal import Decimal
import stripe
import requests
from django.contrib.auth.hashers import check_password


stripe.api_key = settings.STRIPE_SECRET_KEY
PAYPAL_CLIENT_ID = settings.PAYPAL_CLIENT_ID
PAYPAL_SECRET_ID = settings.PAYPAL_SECRET_ID

class MyTokenObtainPairView(TokenObtainPairView):
  serializer_class = api_serializer.MyTokenObtainPairSerializer

class RegisterView(generics.CreateAPIView):
  queryset = User.objects.all()
  permission_classes = [AllowAny]
  serializer_class = api_serializer.RegisterSerializer

def generate_random_otp(length=7):
  otp = ''.join([str(random.randint(0,9)) for _ in range(length)])
  return otp

class PasswordResetEmailVerifyAPIView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = api_serializer.UserSerializer

    def get_object(self):
        email = self.kwargs['email'] # api/v1/password-email-verify/desphixs@gmail.com/

        user = User.objects.filter(email=email).first()

        if user:
            uuidb64 = user.pk
            refresh = RefreshToken.for_user(user)
            refresh_token = str(refresh.access_token)

            user.refresh_token = refresh_token
            user.otp = generate_random_otp()
            user.save()

            link = f"http://localhost:5173/create-new-password/?otp={user.otp}&uuidb64={uuidb64}&refresh_token={refresh_token}"

            context = {
                "link": link,
                "username": user.username
            }

            subject = "Password Rest Email"
            text_body = render_to_string("email/password_reset.txt", context)
            html_body = render_to_string("email/password_reset.html", context)

            msg = EmailMultiAlternatives(
                subject=subject,
                from_email=settings.FROM_EMAIL,
                to=[user.email],
                body=text_body
            )

            msg.attach_alternative(html_body, "text/html")
            msg.send()

            print("link ======", link)
        return user

class PasswordChangeAPIView(generics.CreateAPIView):
  permission_classes = [AllowAny]
  serializer_class = api_serializer.UserSerializer

  def create(self, request, *args, **kwargs):
    otp = request.data['otp']
    uuidb64 = request.data['uuidb64']
    password = request.data['password']

    user = User.objects.get(id=uuidb64, otp=otp)
    if user:
      user.set_password(password)
      user.otp=""
      user.save()

      return Response({"message": "Password changed successfully"}, status=status.HTTP_201_CREATED)
    else:
      return Response({"message": "User doesnot exists"}, status=status.HTTP_404_NOT_FOUND)

class ChangePasswordAPIView(generics.CreateAPIView):
   serializer_class = api_serializer.UserSerializer
   permission_classes = [AllowAny]

   def create(self, request, *args, **kwargs):
      user_id = request.data['user_id']
      old_password = request.data['old_password']
      new_password = request.data['new_password']

      user = User.objects.get(id=user_id)
      if user is not None:
         if check_password(old_password, user.password):
            user.set_password(new_password)
            user.save()
            return Response({"message": "Password changed successfully"}, status=status.HTTP_201_CREATED)
         else:
            return Response({"message": "Old password is incorrect"}, status=status.HTTP_400_BAD_REQUEST)
      else:
         return Response({"message": "User not found"}, status=status.HTTP_404_NOT_FOUND)   

class ProfileAPIView(generics.RetrieveUpdateAPIView):
    serializer_class = api_serializer.ProfileSerializer
    permission_classes = [AllowAny]
    
    def get_object(self):
       user_id = self.kwargs['user_id']
       user = User.objects.get(id=user_id)
       return Profile.objects.get(user=user)
    
      
class CategoryListAPIView(generics.ListAPIView):
    queryset = api_model.Category.objects.filter(active=True)
    serializer_class = api_serializer.CategorySerializer
    permission_classes = [AllowAny]

class CourseListAPIView(generics.ListAPIView):
    queryset = api_model.Course.objects.filter(platform_status="Published", teacher_course_status="Published")
    serializer_class = api_serializer.CourseSerializer
    permission_classes = [AllowAny]

class CourseDetailAPIView(generics.RetrieveAPIView):
    serializer_class = api_serializer.CourseSerializer
    permission_classes = [AllowAny]

    def get_object(self):
       slug = self.kwargs['slug']
       course = api_model.Course.objects.get(slug=slug, platform_status="Published", teacher_course_status="Published")
       return course

class CartAPIView(generics.CreateAPIView):
   queryset = api_model.Cart.objects.all()
   serializer_class = api_serializer.CartSerializer
   permission_classes = [AllowAny]

   def create(self, request, *args, **kwargs):
      course_id = request.data['course_id']
      user_id = request.data['user_id']
      price = request.data['price']
      country_name = request.data['country_name']
      cart_id = request.data['cart_id']

      course = api_model.Course.objects.filter(id=course_id).first()
      if user_id != "undefined":
        user = User.objects.filter(id=user_id).first()
      else:
         user = None
      
      try:
         country_object = api_model.Country.objects.filter(name=country_name).first()
         country = country_object.name
      except:
         country_object = None
         country = "United States"
      
      if country_object:
         tax_rate = country_object.tax_rate/100
      else:
         tax_rate = 0
      
      cart = api_model.Cart.objects.filter(cart_id=cart_id, course=course).first()
      
      if cart:
         cart.course=course
         cart.user=user
         cart.price=price
         cart.tax_fee=Decimal(price)*Decimal(tax_rate)
         cart.country=country
         cart.cart_id=cart_id
         cart.total=Decimal(cart.price)+Decimal(cart.tax_fee)
         cart.save()

         return Response({"message": "Cart Updated Successfully"}, status=status.HTTP_200_OK)
      
      else:
         cart = api_model.Cart()

         cart.course=course
         cart.user=user
         cart.price=price
         cart.tax_fee=Decimal(price)*Decimal(tax_rate)
         cart.country=country
         cart.cart_id=cart_id
         cart.total=Decimal(cart.price)+Decimal(cart.tax_fee)
         cart.save()

         return Response({"message": "Cart Created Successfully"}, status=status.HTTP_201_CREATED)

class CartListAPIView(generics.ListAPIView):
   serializer_class = api_serializer.CartSerializer
   permission_classes = [AllowAny]

   def get_queryset(self):
      cart_id = self.kwargs['cart_id']
      queryset = api_model.Cart.objects.filter(cart_id=cart_id)
      return queryset

class CartItemDeleteAPIView(generics.DestroyAPIView):
   serializer_class = api_serializer.CartSerializer
   permission_classes = [AllowAny]

   def get_object(self):
      cart_id = self.kwargs['cart_id']
      item_id = self.kwargs['item_id']
      return api_model.Cart.objects.filter(cart_id=cart_id, id=item_id).first()

class CartStatsAPIView(generics.RetrieveAPIView):
   serializer_class = api_serializer.CartSerializer
   permission_classes = [AllowAny]
   lookup_field = 'cart_id'
   
   def get_queryset(self):
      cart_id = self.kwargs['cart_id']
      queryset = api_model.Cart.objects.filter(cart_id=cart_id)
      return queryset
   
   def get(self, request, *args, **kwargs):
      queryset = self.get_queryset()
      
      total_price = 0.00
      total_tax = 0.00
      total_total = 0.00
      
      for cart_item in queryset:
         total_price += float(self.calculate_price(cart_item))
         total_tax += float(self.calculate_tax(cart_item))
         total_total += round(float(self.calculate_total(cart_item)), 2)
             
      data = {
         "price": total_price,
         "tax": total_tax,
         "total": total_total,
      }

      return Response(data)

   def calculate_price(self, cart_item):
      return cart_item.price
   
   def calculate_tax(self, cart_item):
      return cart_item.tax_fee
   
   def calculate_total(self, cart_item):
      return cart_item.total

class CreateOrderAPIView(generics.CreateAPIView):
   serializer_class = api_serializer.CartOrderSerializer
   permission_classes = [AllowAny]
   queryset = api_model.CartOrder.objects.all()
   
   def create(self, request, *args, **kwargs):
      full_name = request.data['full_name']
      email = request.data['email']
      country = request.data['country']
      cart_id = request.data['cart_id']
      user_id = request.data['user_id']

      if user_id !=0:
         user = User.objects.get(id=user_id)
      else:
         user = None
      
      cart_items = api_model.Cart.objects.filter(cart_id=cart_id)
      total_price = Decimal(0.00)
      total_tax = Decimal(0.00)
      total_initial_total = Decimal(0.00)
      total_total = Decimal(0.00)

      order = api_model.CartOrder.objects.create(
         full_name=full_name,
         email=email,
         country=country,
         student=user,
      )

      for c in cart_items:
         api_model.CartOrderItem.objects.create(
            order=order,
            course=c.course,
            price=c.price,
            tax_fee=c.tax_fee,
            total=c.total, 
            initial_total=c.total,
            teacher=c.course.teacher
         )

         total_price += Decimal(c.price)
         total_tax += Decimal(c.tax_fee)
         total_initial_total += Decimal(c.total)
         total_total += Decimal(c.total)
         order.teachers.add(c.course.teacher)
      
      order.sub_total = total_price
      order.tax_fee = total_tax
      order.initial_total = total_initial_total
      order.total = total_total
      order.save()
      
      return Response({"message": "Order Created Successfully", "order_oid": order.oid}, status=status.HTTP_201_CREATED)

class CheckoutAPIView(generics.RetrieveAPIView):
   serializer_class = api_serializer.CartOrderSerializer
   permission_classes = [AllowAny]
   queryset = api_model.CartOrder.objects.all()
   lookup_field = 'oid'

class CouponApplyAPIView(generics.CreateAPIView):
   serializer_class = api_serializer.CouponSerializer
   permission_classes = [AllowAny]

   def create(self,request, *args, **kwargs):
      order_oid = request.data['order_oid']
      coupon_code = request.data['coupon_code']

      order = api_model.CartOrder.objects.get(oid=order_oid)
      coupon = api_model.Coupon.objects.get(code=coupon_code)
      if coupon:
         order_items = api_model.CartOrderItem.objects.filter(order=order, teacher=coupon.teacher)
         for o in order_items:
            if not coupon in o.coupons.all():
                discount = o.total*coupon.discount/100
                o.total -= discount
                o.price -= discount
                o.saved += discount
                o.applied_coupon = True
                o.coupons.add(coupon)
                
                order.coupons.add(coupon)
                order.total -= discount
                order.sub_total -= discount
                order.saved += discount

                o.save()
                order.save()
                coupon.used_by.add(order.student)

                return Response({"message": "Coupon found and Activated"}, status=status.HTTP_201_CREATED)
            else:
               return Response({"message": "Coupon already applied"}, status=status.HTTP_200_OK)
      else:
         return Response({"message": "Coupon not found"}, status=status.HTTP_404_NOT_FOUND)

class StripeCheckoutAPIView(generics.CreateAPIView):
   serializer_class = api_serializer.CartOrderSerializer
   permission_classes = [AllowAny]

   def create(self, request, *args, **kwargs):
      order_oid = self.kwargs['order_oid']
      order = api_model.CartOrder.objects.get(oid=order_oid)
      
      if not order:
         return Response({"message": "Order Not Found"}, status=status.HTTP_404_NOT_FOUND)
      
      try:
         checkout_session = stripe.checkout.Session.create(
            customer_email=order.email,
            payment_method_types=['card'],
            line_items=[
               {
                'price_data': {
                   'currency': 'usd',
                   'product_data': {
                     'name': order.full_name,
                   },
                   'unit_amount': int(order.total*100), 
                },
                'quantity': 1,
            }
            ],
            mode='payment',
            success_url=settings.FRONTEND_SITE_URL + '/payment-success/' + order.oid + '?session_id={CHECKOUT_SESSION_ID}',

            cancel_url=settings.FRONTEND_SITE_URL + '/payment-failed/',
         )
         print(checkout_session)

         order.stripe_session_id=checkout_session.id
         return redirect(checkout_session.url)
      except stripe.error.StripeError as e:
         return Response({"message": f"Something went wrong while trying to payment. Error: {str(e)}"})
      
def get_access_token(client_id, secret_key):
   token_url="https://api.sandbox.paypal.com/v1/oauth2/token"
   data = {'grant_type': 'client_credentials'}
   auth = (client_id, secret_key)
   response = requests.post(token_url, auth=auth, data=data)

   if response.status_code == 200:
      print("Access Token ===", response.json()['access_token'])
      return response.json()['access_token']
   else:
      raise Exception(f"Failed to get access token from paypal {response.status_code}")

class PaymentSuccessAPIView(generics.CreateAPIView):
   serializer_class = api_serializer.CartOrderSerializer
   queryset = api_model.CartOrder.objects.all()

   def creata(self, request, *args, **kwargs):
      order_oid = request.data['order_oid']
      session_id = request.data['session_id']
      paypal_order_id = request.data['paypal_order_id']

      order = api_model.CartOrder.objects.get(oid=order_oid)
      order_items = api_model.CartOrderItem.objects.filter(order=order)

      #Paypal Payment Success

      if paypal_order_id != "null":
         paypal_api_url = f"https://api-m.sandbox.paypal.com/v2/checkout/orders/{paypal_order_id}"
         headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {get_access_token(PAYPAL_CLIENT_ID, PAYPAL_SECRET_ID)}"
         }
         response = request.get(paypal_api_url, headers=headers)
         if response.status_code == 200:
            paypal_order_data = response.json()
            paypal_payment_status = paypal_order_data['status']
            if paypal_payment_status == "COMPLETED":
               if order.payment_status == "Processing":
                  order.payment_status = "Paid"
                  order.save()
                  api_model.Notification.objects.create(user=order.student, order=order, type='Course Enrollment Completed')

                  for o in order_items:
                     api_model.Notification.objects.create(teacher=o.teacher, order=order, order_item=o, type='New Order')
                     api_model.EnrolledCourse.objects.create(
                        course=o.course,
                        user=order.student,
                        teacher=o.teacher,
                        order_item=o
                     )
                  return Response({"message": "Payment Successful. Thank You"})
               else:
                  return Response({"message": "You have already paid. Thank You"})
            else:
               return Response({"message": "Payment Failed"})
         else:
            return Response({"message": f"Failed to get paypal order data. Error: {response.status_code}"})
               

      #Stripe Payment Success
      if session_id!= "null":
            session = stripe.checkout.Session.retrieve(session_id)
            if session.payment_status == "paid":
               if order.payment_status == "Processing":
                  order.payment_status = "Paid"
                  order.save()
                  api_model.Notification.objects.create(user=order.student, order=order, type='Course Enrollment Completed')

                  for o in order_items:
                     api_model.Notification.objects.create(teacher=o.teacher, order=order, order_item=o, type='New Order')
                     api_model.EnrolledCourse.objects.create(
                        course=o.course,
                        user=order.student,
                        teacher=o.teacher,
                        order_item=o
                     )

                  return Response({"message": "Payment Successful."})
               else:
                  return Response({"message": "Already Paid."})
            else:
               return Response({"message": "Payment Failed"})

class SearchCourseAPIView(generics.ListAPIView):
   serializer_class = api_serializer.CourseSerializer
   permission_classes = [AllowAny]
   
   def get_queryset(self):
      query = self.request.GET.get['query']
      return api_model.Course.objects.filter(title__icontains=query, platform_status="Published", teacher_course_status="Published")

class StudentSummaryAPIView(generics.ListAPIView):
   serializer_class = api_serializer.StudentSummarySerializer
   permission_classes = [AllowAny]

   def get_queryset(self):
      user_id = self.kwargs['user_id']
      user = User.objects.get(id=user_id)

      total_courses = api_model.EnrolledCourse.objects.filter(user=user).count()
      completed_lessons = api_model.CompletedLesson.objects.filter(user=user).count()
      achieved_certificates = api_model.Certificate.objects.filter(user=user).count()
      return {
         "total_courses": total_courses,
         "completed_lessons": completed_lessons,
         "achieved_certificates": achieved_certificates,
      }
   
   def list(self, requset, *args, **kwargs):
      queryset = self.get_queryset()
      serializer = self.get_serializer(queryset, many=True)
      return Response(serializer.data)

class StudentCourseListAPIView(generics.ListAPIView):
   serializer_class = api_serializer.EnrolledCourseSerializer
   permission_classes = [AllowAny]
   
   def get_queryset(self):
      user_id = self.kwargs['user_id']
      user = User.objects.get(id=user_id)
      return api_model.EnrolledCourse.objects.filter(user=user)

class StudentCourseDetailAPIView(generics.RetrieveAPIView):
   serializer_class = api_serializer.EnrolledCourseSerializer
   permission_classes = [AllowAny]
   lookup_field = 'enrollment_id'
   
   def get_object(self):
      user_id = self.kwargs['user_id']
      enrollment_id = self.kwargs['enrollment_id']
      user = User.objects.get(id=user_id)
      return api_model.EnrolledCourse.objects.get(user=user, enrollment_id=enrollment_id)

class StudentCourseCompletedCreateAPIView(generics.CreateAPIView):
   serializer_class = api_serializer.CompletedLessonSerializer
   permission_classes = [AllowAny]

   def create(self, request, *args, **kwargs):
      user_id = request.data['user_id']
      course_id = request.data['course_id']
      variant_item_id = self.kwargs['variant_item_id']

      user = User.objects.get(id=user_id)
      course = api_model.Course.objects.get(id=course_id)
      variant_item = api_model.VariantItem.objects.get(variant_item_id=variant_item_id)
      
      completed_lesson = api_model.CompletedLesson.objects.filter(
         user=user,
         course=course,
         variant_item=variant_item
      ).first()
      if completed_lesson:
         completed_lesson.delete()
         return Response({"message": "Course Mark as not completed"})
      else:
         api_model.CompletedLesson.objects.create(
            user=user,
            course=course,
            variant_item=variant_item
         )   
         return Response({"message": "Course Mark as completed"})
      
class StudentNoteCreateAPIView(generics.ListCreateAPIView):
   serializer_class = api_serializer.NoteSerializer
   permission_classes = [AllowAny]
   
   def get_queryset(self):
      user_id = self.kwargs['user_id']
      enrollment_id = self.kwargs['enrollment_id']
      
      user = User.objects.get(id=user_id)
      enrolled = api_model.EnrolledCourse.objects.get(enrollment_id=enrollment_id)
      
      return api_model.Note.objects.filter(user=user, course=enrolled.course)
   
   def create(self, request, *args, **kwargs):
      user_id = request.data['user_id']
      enrollment_id = request.data['enrollment_id']
      title = request.data['title']
      note = request.data['note']

      user = User.objects.get(id=user_id)
      enrolled = api_model.EnrolledCourse.objects.get(enrollment_id=enrollment_id)
      
      api_model.Note.objects.create(
            user=user,
            course=enrolled.course,
            enrollment=enrolled,
            note=note,
            title=title
         )   
      return Response({"message": "Note created successfully"}, status=status.HTTP_201_CREATED)

class StudentNoteDetailAPIView(generics.RetrieveUpdateAPIView):
   serializer_class = api_serializer.NoteSerializer
   permission_classes = [AllowAny]

   def get_object(self):
      user_id = self.kwargs['user_id']
      enrollment_id = self.kwargs['enrollment_id']
      note_id = self.kwargs['note_id']

      user = User.objects.get(id=user_id)
      enrolled = api_model.EnrolledCourse.objects.get(enrollment_id=enrollment_id)
      note = api_model.Note.objects.get(user=user,course=enrolled.course,id=note_id)
      return note

class StudentRateCourseCreateAPIView(generics.CreateAPIView):
   serializer_class = api_serializer.ReviewSerializer
   permission_classes = [AllowAny]
   
   def create(self, request, *args, **kwargs):
      user_id = request.data['user_id']
      course_id = request.data['course_id']
      rating = request.data['rating']
      review = request.data['review']
      
      user = User.objects.get(id=user_id)
      course = api_model.Course.objects.get(id=course_id)
      
      api_model.Review.objects.create(
            user=user,
            course=course,
            rating=rating,
            review=review,
            active=True,
            )
      return Response({"message": "Review created successfully"}, status=status.HTTP_201_CREATED)

class StudentRateCourseUpdateAPIView(generics.RetrieveUpdateAPIView):
   serializer_class = api_serializer.ReviewSerializer
   permission_classes = [AllowAny]
   
   def get_object(self):
      user_id = self.kwargs['user_id']
      review_id = self.kwargs['review_id']
      
      user = User.objects.get(id=user_id)
      return api_model.Review.objects.get(id=review_id, user=user)

class StudentWishListListCreateAPIView(generics.ListCreateAPIView):
   serializer_class = api_serializer.WishlistSerializer
   permission_classes = [AllowAny]
   
   def get_queryset(self):
      user_id = self.kwargs['user_id']
      
      user = User.objects.get(id=user_id)
      return api_model.Wishlist.objects.filter(user=user)
   
   def create(self, request, *args, **kwargs):
      user_id = request.data['user_id']
      course_id = request.data['course_id']
      
      user = User.objects.get(id=user_id)
      course = api_model.Course.objects.get(id=course_id)
      wishlist = api_model.Wishlist.objects.filter(
            user=user,
            course=course
         ).first()
      if wishlist:
         wishlist.delete()
         return Response({"message": "Course removed from wishlist"})
      else:
         api_model.Wishlist.objects.create(
            user=user,
            course=course
         )
         return Response({"message": "Course added to wishlist"})
      
class QuestionAnswerListCreateAPIView(generics.ListCreateAPIView):
   serializer_class = api_serializer.Question_AnswerSerializer
   permission_classes = [AllowAny]
   
   def get_queryset(self):
      course_id = self.kwargs['course_id']
      course = api_model.Course.objects.get(id=course_id)
      return api_model.Question_Answer.objects.filter(course=course)
   
   def create(self, request, *args, **kwargs):
      course_id = request.data['course_id']
      user_id = request.data['user_id']
      title = request.data['title']
      message = request.data['message']
      
      user = User.objects.get(id=user_id)
      course = api_model.Course.objects.get(id=course_id)
      
      question = api_model.Question_Answer.objects.create(
            course=course,
            user=user,
            title=title,
   
         )
      api_model.Question_Answer_Message.objects.create(
         course=course,
         user=user,
         message=message,
         question=question
      )
      return Response({"message": "Group COnversation started"}, status=status.HTTP_201_CREATED)

class QuestionAnswerMessageSendAPIView(generics.CreateAPIView):
   serializer_class = api_serializer.Question_Answer_MessagesSerializer
   permission_classes = [AllowAny]
   
   def create(self, request, *args, **kwargs):
      course_id = self.kwargs['course_id']
      qa_id = self.kwargs['qa_id']
      user_id = request.data['user_id']
      message = request.data['message']
      
      user = User.objects.get(id=user_id)
      course = api_model.Course.objects.get(id=course_id)
      question = api_model.Question_Answer.objects.get(qa_id=qa_id)
      
      api_model.Question_Answer_Message.objects.create(
            course=course,
            user=user,
            message=message,
            question=question
      )
      question_serializer = api_serializer.Question_AnswerSerializer(question)
      return Response({"message": "Message sent successfully", "question": question_serializer.data}, status=status.HTTP_201_CREATED)

from datetime import datetime, timedelta
from django.db import models

class TeacherSummaryAPIView(generics.ListAPIView):
   serializer_class = api_serializer.TeacherSummarySerializer
   permission_classes = [AllowAny]

   def get_queryset(self):
      teacher_id = self.kwargs['teacher_id']
      teacher = api_model.Teacher.objects.get(id=teacher_id)
      
      one_month_ago = datetime.today()-timedelta(days=28)
      total_courses = api_model.Course.objects.filter(teacher=teacher).count()
      total_revenue = api_model.CartOrderItem.objects.filter(teacher=teacher, order__payment_status="Paid").aggregate(total_revenue=models.Sum("price"))['total_revenue'] or 0
      monthly_revenue = api_model.CartOrderItem.objects.filter(teacher=teacher, order__payment_status="Paid", date__gte = one_month_ago).aggregate(total_revenue=models.Sum("price"))['total_revenue'] or 0
      enrolled_courses = api_model.EnrolledCourse.objects.filter(teacher=teacher)
      unique_student_ids = set()
      students = []

      for course in enrolled_courses:
         if course.user_id not in unique_student_ids:
            user = User.objects.get(id=course.user_id)
            student = {
               "full_name": user.profile.full_name,
               "image": user.profile.image.url,
               "country": user.profile.country,
               "date": course.date
            }
            students.append(student)
            unique_student_ids.add(course.user_id)
      
      return [{
         "total_courses": total_courses,
         "total_revenue": total_revenue,
         "monthly_revenue": monthly_revenue,
         "total_students": len(students)
      }]
   
   def list(self,request, *args, **kwargs):
      queryset = self.get_queryset()
      serializer = self.get_serializer(queryset, many=True)
      return Response(serializer.data)

class TeacherCourseListAPIView(generics.ListAPIView):
   serializer_class = api_serializer.CourseSerializer
   permission_classes = [AllowAny]
   
   def get_queryset(self):
      teacher_id = self.kwargs['teacher_id']
      teacher = api_model.Teacher.objects.get(id=teacher_id)
      return api_model.Course.objects.filter(teacher=teacher)

class TeacherReviewListAPIView(generics.ListAPIView):
   serializer_class = api_serializer.ReviewSerializer
   permission_classes = [AllowAny]
   
   def get_queryset(self):
      teacher_id = self.kwargs['teacher_id']
      teacher = api_model.Teacher.objects.get(id=teacher_id)
      return api_model.Review.objects.filter(course__teacher=teacher)
   
class TeacherReviewDetailAPIView(generics.RetrieveUpdateAPIView):
   serializer_class = api_serializer.ReviewSerializer
   permission_classes = [AllowAny]
   
   def get_object(self):
      teacher_id = self.kwargs['teacher_id']
      review_id = self.kwargs['review_id']
      teacher = api_model.Teacher.objects.get(id=teacher_id)
      return api_model.Review.objects.get(id=review_id, course__teacher=teacher)

from rest_framework import viewsets

class TeacherStudentsListAPIView(viewsets.ViewSet):

   def list(self, request, teacher_id=None):
      teacher = api_model.Teacher.objects.get(id=teacher_id)
      enrolled_courses = api_model.EnrolledCourse.objects.filter(teacher=teacher)
      unique_student_ids = set()
      students = []
      
      for course in enrolled_courses:
         if course.user_id not in unique_student_ids:
            user = User.objects.get(id=course.user_id)
            student = {
               "full_name": user.profile.full_name,
               "image": user.profile.image.url,
               "country": user.profile.country,
               "date": course.date
            }
            students.append(student)
            unique_student_ids.add(course.user_id)
      
      return Response(students)

from django.db.models.functions import ExtractMonth
from rest_framework.decorators import api_view

@api_view(("GET", ))
def TeacherAllMonthEarningAPIView(request, teacher_id):
    teacher = api_model.Teacher.objects.get(id=teacher_id)
    monthly_earning_tracker = (
        api_model.CartOrderItem.objects
        .filter(teacher=teacher, order__payment_status="Paid")
        .annotate(
            month=ExtractMonth("date")
        )
        .values("month")
        .annotate(
            total_earning=models.Sum("price")
        )
        .order_by("month")
    )

    return Response(monthly_earning_tracker)

class TeacherBestSellingCourseAPIView(viewsets.ViewSet):

    def list(self, request, teacher_id=None):
        teacher = api_model.Teacher.objects.get(id=teacher_id)
        courses_with_total_price = []
        courses = api_model.Course.objects.filter(teacher=teacher)

        for course in courses:
            revenue = course.enrolledcourse_set.aggregate(total_price=models.Sum('order_item__price'))['total_price'] or 0
            sales = course.enrolledcourse_set.count()

            courses_with_total_price.append({
                'course_image': course.image.url,
                'course_title': course.title,
                'revenue': revenue,
                'sales': sales,
            })

        return Response(courses_with_total_price)
    
class TeacherCourseOrdersListAPIView(generics.ListAPIView):
    serializer_class = api_serializer.CartOrderItemSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        teacher_id = self.kwargs['teacher_id']
        teacher = api_model.Teacher.objects.get(id=teacher_id)

        return api_model.CartOrderItem.objects.filter(teacher=teacher)

class TeacherQuestionAnswerListAPIView(generics.ListAPIView):
    serializer_class = api_serializer.Question_AnswerSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        teacher_id = self.kwargs['teacher_id']
        teacher = api_model.Teacher.objects.get(id=teacher_id)
        return api_model.Question_Answer.objects.filter(course__teacher=teacher)
    
class TeacherCouponListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = api_serializer.CouponSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        teacher_id = self.kwargs['teacher_id']
        teacher = api_model.Teacher.objects.get(id=teacher_id)
        return api_model.Coupon.objects.filter(teacher=teacher)
    
class TeacherCouponDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = api_serializer.CouponSerializer
    permission_classes = [AllowAny]
    
    def get_object(self):
        teacher_id = self.kwargs['teacher_id']
        coupon_id = self.kwargs['coupon_id']
        teacher = api_model.Teacher.objects.get(id=teacher_id)
        return api_model.Coupon.objects.get(teacher=teacher, id=coupon_id)
    
class TeacherNotificationListAPIView(generics.ListAPIView):
    serializer_class = api_serializer.NotificationSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        teacher_id = self.kwargs['teacher_id']
        teacher = api_model.Teacher.objects.get(id=teacher_id)
        return api_model.Notification.objects.filter(teacher=teacher, seen=False)
    
class TeacherNotificationDetailAPIView(generics.RetrieveUpdateAPIView):
    serializer_class = api_serializer.NotificationSerializer
    permission_classes = [AllowAny]

    def get_object(self):
        teacher_id = self.kwargs['teacher_id']
        noti_id = self.kwargs['noti_id']
        teacher = api_model.Teacher.objects.get(id=teacher_id)
        return api_model.Notification.objects.get(teacher=teacher, id=noti_id)

from distutils.util import strtobool    
class CourseCreateAPIView(generics.CreateAPIView):
    querysect = api_model.Course.objects.all()
    serializer_class = api_serializer.CourseSerializer
    permisscion_classes = [AllowAny]

    def perform_create(self, serializer):
        serializer.is_valid(raise_exception=True)
        course_instance = serializer.save()

        variant_data = []
        for key, value in self.request.data.items():
            if key.startswith('variant') and '[variant_title]' in key:
                index = key.split('[')[1].split(']')[0]
                title = value

                variant_dict = {'title': title}
                item_data_list = []
                current_item = {}
                variant_data = []

                for item_key, item_value in self.request.data.items():
                    if f'variants[{index}][items]' in item_key:
                        field_name = item_key.split('[')[-1].split(']')[0]
                        if field_name == "title":
                            if current_item:
                                item_data_list.append(current_item)
                            current_item = {}
                        current_item.update({field_name: item_value})
                    
                if current_item:
                    item_data_list.append(current_item)

                variant_data.append({'variant_data': variant_dict, 'variant_item_data': item_data_list})

        for data_entry in variant_data:
            variant = api_model.Variant.objects.create(title=data_entry['variant_data']['title'], course=course_instance)

            for item_data in data_entry['variant_item_data']:
                preview_value = item_data.get("preview")
                preview = bool(strtobool(str(preview_value))) if preview_value is not None else False

                api_model.VariantItem.objects.create(
                    variant=variant,
                    title=item_data.get("title"),
                    description=item_data.get("description"),
                    file=item_data.get("file"),
                    preview=preview,
                )

    def save_nested_data(self, course_instance, serializer_class, data):
        serializer = serializer_class(data=data, many=True, context={"course_instance": course_instance})
        serializer.is_valid(raise_exception=True)
        serializer.save(course=course_instance) 


from django.core.files.uploadedfile import InMemoryUploadedFile

class CourseUpdateAPIView(generics.RetrieveUpdateAPIView):
    querysect = api_model.Course.objects.all()
    serializer_class = api_serializer.CourseSerializer
    permisscion_classes = [AllowAny]

    def get_object(self):
        teacher_id = self.kwargs['teacher_id']
        course_id = self.kwargs['course_id']

        teacher = api_model.Teacher.objects.get(id=teacher_id)
        course = api_model.Course.objects.get(course_id=course_id)

        return course
    
    def update(self, request, *args, **kwargs):
        course = self.get_object()
        serializer = self.get_serializer(course, data=request.data)
        serializer.is_valid(raise_exception=True)

        if "image" in request.data and isinstance(request.data['image'], InMemoryUploadedFile):
            course.image = request.data['image']
        elif 'image' in request.data and str(request.data['image']) == "No File":
            course.image = None
        
        if 'file' in request.data and not str(request.data['file']).startswith("http://"):
            course.file = request.data['file']

        if 'category' in request.data['category'] and request.data['category'] != 'NaN' and request.data['category'] != "undefined":
            category = api_model.Category.objects.get(id=request.data['category'])
            course.category = category

        self.perform_update(serializer)
        self.update_variant(course, request.data)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def update_variant(self, course, request_data):
        for key, value in request_data.items():
            if key.startswith("variants") and '[variant_title]' in key:

                index = key.split('[')[1].split(']')[0]
                title = value

                id_key = f"variants[{index}][variant_id]"
                variant_id = request_data.get(id_key)

                variant_data = {'title': title}
                item_data_list = []
                current_item = {}

                for item_key, item_value in request_data.items():
                    if f'variants[{index}][items]' in item_key:
                        field_name = item_key.split('[')[-1].split(']')[0]
                        if field_name == "title":
                            if current_item:
                                item_data_list.append(current_item)
                            current_item = {}
                        current_item.update({field_name: item_value})
                    
                if current_item:
                    item_data_list.append(current_item)

                existing_variant = course.variant_set.filter(id=variant_id).first()

                if existing_variant:
                    existing_variant.title = title
                    existing_variant.save()

                    for item_data in item_data_list[1:]:
                        preview_value = item_data.get("preview")
                        preview = bool(strtobool(str(preview_value))) if preview_value is not None else False

                        variant_item = api_model.VariantItem.objects.filter(variant_item_id=item_data.get("variant_item_id")).first()

                        if not str(item_data.get("file")).startswith("http://"):
                            if item_data.get("file") != "null":
                                file = item_data.get("file")
                            else:
                                file = None
                            
                            title = item_data.get("title")
                            description = item_data.get("description")

                            if variant_item:
                                variant_item.title = title
                                variant_item.description = description
                                variant_item.file = file
                                variant_item.preview = preview
                            else:
                                variant_item = api_model.VariantItem.objects.create(
                                    variant=existing_variant,
                                    title=title,
                                    description=description,
                                    file=file,
                                    preview=preview
                                )
                        
                        else:
                            title = item_data.get("title")
                            description = item_data.get("description")

                            if variant_item:
                                variant_item.title = title
                                variant_item.description = description
                                variant_item.preview = preview
                            else:
                                variant_item = api_model.VariantItem.objects.create(
                                    variant=existing_variant,
                                    title=title,
                                    description=description,
                                    preview=preview
                                )
                        
                        variant_item.save()

                else:
                    new_variant = api_model.Variant.objects.create(
                        course=course, title=title
                    )

                    for item_data in item_data_list:
                        preview_value = item_data.get("preview")
                        preview = bool(strtobool(str(preview_value))) if preview_value is not None else False

                        api_model.VariantItem.objects.create(
                            variant=new_variant,
                            title=item_data.get("title"),
                            description=item_data.get("description"),
                            file=item_data.get("file"),
                            preview=preview,
                        )

    def save_nested_data(self, course_instance, serializer_class, data):
        serializer = serializer_class(data=data, many=True, context={"course_instance": course_instance})
        serializer.is_valid(raise_exception=True)
        serializer.save(course=course_instance) 


class CourseDetailAPIView(generics.RetrieveDestroyAPIView):
    serializer_class = api_serializer.CourseSerializer
    permission_classes = [AllowAny]

    def get_object(self):
        course_id = self.kwargs['course_id']
        return api_model.Course.objects.get(course_id=course_id)


class CourseVariantDeleteAPIView(generics.DestroyAPIView):
    serializer_class = api_serializer.VariantSerializer
    permission_classes = [AllowAny]

    def get_object(self):
        variant_id = self.kwargs['variant_id']
        teacher_id = self.kwargs['teacher_id']
        course_id = self.kwargs['course_id']

        print("variant_id ========", variant_id)

        teacher = api_model.Teacher.objects.get(id=teacher_id)
        course = api_model.Course.objects.get(teacher=teacher, course_id=course_id)
        return api_model.Variant.objects.get(id=variant_id)
    
class CourseVariantItemDeleteAPIVIew(generics.DestroyAPIView):
    serializer_class = api_serializer.VariantItemSerializer
    permission_classes = [AllowAny]

    def get_object(self):
        variant_id = self.kwargs['variant_id']
        variant_item_id = self.kwargs['variant_item_id']
        teacher_id = self.kwargs['teacher_id']
        course_id = self.kwargs['course_id']


        teacher = api_model.Teacher.objects.get(id=teacher_id)
        course = api_model.Course.objects.get(teacher=teacher, course_id=course_id)
        variant = api_model.Variant.objects.get(variant_id=variant_id, course=course)
        return api_model.VariantItem.objects.get(variant=variant, variant_item_id=variant_item_id)
   
   
   

   




