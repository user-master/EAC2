import time
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.contrib.auth.models import User, Permission
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

class MySeleniumTests(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        """
        Configuración inicial del test:
         - Se inicia Firefox (modo headless opcional).
         - Se establece una espera implícita.
         - Se crea un superusuario (isard/pirineus) para acceder al admin.
        """
        super().setUpClass()
        opts = FirefoxOptions()
        # Para ver el navegador en acción, deja comentada la siguiente línea:
        # opts.add_argument("--headless")
        cls.selenium = webdriver.Firefox(options=opts)
        cls.selenium.implicitly_wait(5)
        # Crear superusuario para el admin
        user = User.objects.create_user("isard", "isard@isardvdi.com", "pirineus")
        user.is_superuser = True
        user.is_staff = True
        user.save()

    @classmethod
    def tearDownClass(cls):
        """Cierra el navegador al finalizar los tests."""
        cls.selenium.quit()
        super().tearDownClass()

    def admin_login(self, username, password):
        """
        Realiza el login en el panel de administración:
         1. Navega a /admin/login/.
         2. Espera a que aparezcan los campos y rellena las credenciales.
         3. Hace clic en 'Log in' y espera a que aparezca el formulario de logout (id="logout-form").
        """
        self.selenium.get(f'{self.live_server_url}/admin/login/')
        wait = WebDriverWait(self.selenium, 15)
        username_input = wait.until(EC.presence_of_element_located((By.NAME, "username")))
        password_input = self.selenium.find_element(By.NAME, "password")
        username_input.send_keys(username)
        password_input.send_keys(password)
        login_button = self.selenium.find_element(By.XPATH, "//input[@value='Log in' or @value='Iniciar sesión']")
        login_button.click()
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#logout-form")))
        except TimeoutException:
            print("Tiempo de espera agotado en admin_login. Página actual:")
            print(self.selenium.page_source)
            raise

    def create_user_via_admin(self, username, password, is_staff=False, user_permissions=[]):
        """
        Crea un usuario mediante la interfaz de administración:
         1. Navega a /admin/auth/user/ y pulsa "Add user" en la fila de Users.
         2. Espera a que se cargue el formulario (campo 'id_username') y lo rellena.
         3. Envía el formulario. Si hay una segunda pantalla, marca 'is_staff' y asigna permisos.
         4. Hace clic en guardar y espera un mensaje de éxito.
         IMPORTANTE: Se imprimen en consola las opciones disponibles en el selector de permisos.
        """
        self.selenium.get(f'{self.live_server_url}/admin/auth/user/')
        wait = WebDriverWait(self.selenium, 15)
        try:
            # Buscamos el enlace "Add user" dentro de la fila de Users
            add_user_link = wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "tr.model-user a.addlink")
            ))
        except TimeoutException:
            raise AssertionError("No se encontró el enlace para añadir usuario en la fila de Users.")
        add_user_link.click()
        username_field = wait.until(EC.presence_of_element_located((By.ID, "id_username")))
        username_field.send_keys(username)
        password1_field = wait.until(EC.presence_of_element_located((By.ID, "id_password1")))
        password1_field.send_keys(password)
        password2_field = self.selenium.find_element(By.ID, "id_password2")
        password2_field.send_keys(password)
        save_button = self.selenium.find_element(By.NAME, "_save")
        save_button.click()
        if is_staff:
            try:
                is_staff_checkbox = wait.until(EC.presence_of_element_located((By.ID, "id_is_staff")))
                if not is_staff_checkbox.is_selected():
                    is_staff_checkbox.click()
            except TimeoutException:
                pass
        if user_permissions:
            try:
                permissions_select_elem = wait.until(EC.presence_of_element_located((By.ID, "id_user_permissions")))
                permissions_select = Select(permissions_select_elem)
                print("Opciones disponibles en el selector de permisos:")
                for option in permissions_select.options:
                    print("   ->", option.text)
                for perm in user_permissions:
                    permissions_select.select_by_visible_text(perm)
            except TimeoutException:
                pass
        final_save_button = self.selenium.find_element(By.NAME, "_save")
        final_save_button.click()
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".success")))

    def test_staff_user_view_users(self):
        """
        Flujo del test:
         1. Inicia sesión como superusuario (isard/pirineus).
         2. Crea un usuario staff (staff1) asignándole el permiso
            "Authentication and Authorization | user | Can view user".
         3. Crea tres usuarios normales: user1, user2 y user3.
         4. (Workaround) Actualiza programáticamente los permisos de staff1 para que tenga
            únicamente el permiso "view_user" (sin "change_user").
         5. Cierra la sesión y vuelve a iniciar sesión como staff1.
         6. Accede a /admin/auth/user/ y, para cada usuario, hace clic en el enlace del nombre;
            se comprueba que al intentar editar se muestra un mensaje de permiso insuficiente (por ejemplo, 403).
        """
        # 1. Iniciar sesión como superusuario
        self.admin_login("isard", "pirineus")
        
        # 2. Crear el usuario staff usando la interfaz de admin
        self.create_user_via_admin(
            "staff1", "staffpass", is_staff=True,
            user_permissions=["Authentication and Authorization | user | Can view user"]
        )
        
        # 3. Actualizar programáticamente los permisos de staff1 para que tenga únicamente "view_user"
        staff1 = User.objects.get(username="staff1")
        staff1.user_permissions.clear()
        view_perm = Permission.objects.get(codename="view_user", content_type__app_label="auth")
        staff1.user_permissions.add(view_perm)
        staff1.save()
        print(f"Permisos de staff1 actualizados: {staff1.get_all_permissions()}")
        
        # 4. Crear tres usuarios normales
        for i in range(1, 4):
            self.create_user_via_admin(f"user{i}", "userpass")
        
        # 5. Cerrar sesión
        logout_button = self.selenium.find_element(By.CSS_SELECTOR, "#logout-form button")
        logout_button.click()
        
        # 6. Iniciar sesión como staff1
        self.admin_login("staff1", "staffpass")
        self.selenium.get(f'{self.live_server_url}/admin/auth/user/')
        wait = WebDriverWait(self.selenium, 15)
        # 7. Para cada usuario, hacer clic en el enlace del nombre y comprobar que se muestra un mensaje de error
        for i in range(1, 4):
            user_text = f"user{i}"
            try:
                row = wait.until(EC.presence_of_element_located(
                    (By.XPATH, f"//tr[contains(., '{user_text}')]")
                ))
            except TimeoutException:
                assert False, f"El usuario {user_text} no se muestra en la lista."
            try:
                # Localizar el enlace del nombre del usuario
                link = row.find_element(By.XPATH, f".//a[text()='{user_text}']")
                link.click()
            except NoSuchElementException:
                assert False, f"No se encontró el enlace para {user_text} (se esperaba que existiera)."
            
            # Esperar a que la página de edición (o intento) cargue y comprobar que muestra un error de permisos.
            page_source = self.selenium.page_source.lower()
            if "permission" not in page_source and "forbid" not in page_source:
                assert False, f"Al hacer clic en {user_text}, la página no indica falta de permisos. Página:\n{self.selenium.page_source}"
            
            # Volver al listado de usuarios
            self.selenium.get(f'{self.live_server_url}/admin/auth/user/')
