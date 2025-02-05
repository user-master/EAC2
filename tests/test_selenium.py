from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.contrib.auth.models import User
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import time


class MySeleniumTests(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        """
        Configuración inicial del test:
        - Inicia Firefox con interfaz gráfica (sin headless).
        - Configura un superusuario para el test.
        """
        super().setUpClass()
        opts = FirefoxOptions()
        # Mostrar el navegador
        # opts.add_argument("--headless")  # COMENTADA PARA VER LA INTERFAZ
        cls.selenium = webdriver.Firefox(options=opts)
        cls.selenium.implicitly_wait(5)
        # Crear superusuario
        user = User.objects.create_user("isard", "isard@isardvdi.com", "pirineus")
        user.is_superuser = True
        user.is_staff = True
        user.save()

    @classmethod
    def tearDownClass(cls):
        """Cerrar el navegador al finalizar los tests."""
        cls.selenium.quit()
        super().tearDownClass()

    def admin_login(self, username, password):
        """
        Realiza el login en el panel de administración.
        """
        self.selenium.get(f"{self.live_server_url}/admin/login/")
        wait = WebDriverWait(self.selenium, 15)
        username_input = wait.until(EC.presence_of_element_located((By.NAME, "username")))
        password_input = self.selenium.find_element(By.NAME, "password")
        username_input.send_keys(username)
        password_input.send_keys(password)
        login_button = self.selenium.find_element(By.XPATH, "//input[@value='Log in']")
        login_button.click()

    def admin_logout(self):
        """
        Cierra la sesión del usuario actual en el panel de administración.
        """
        # Asegurarse de estar en el panel de administración
        self.selenium.get(f"{self.live_server_url}/admin/")
        wait = WebDriverWait(self.selenium, 15)

        # Buscar y hacer clic en el botón de logout
        logout_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[text()='Log out']")))
        logout_button.click()

    def create_user_and_assign_permission(self, username, password, permission_to_assign=None, is_staff=False):
        """
        Crea un usuario en el panel de administración con Selenium.
        """
        wait = WebDriverWait(self.selenium, 15)

        # 1️⃣ Crear usuario nuevo
        self.selenium.get(f"{self.live_server_url}/admin/auth/user/")
        add_user_link = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "tr.model-user a.addlink")))
        add_user_link.click()
        wait.until(EC.presence_of_element_located((By.ID, "id_username"))).send_keys(username)
        wait.until(EC.presence_of_element_located((By.ID, "id_password1"))).send_keys(password)
        wait.until(EC.presence_of_element_located((By.ID, "id_password2"))).send_keys(password)
        save_button = self.selenium.find_element(By.NAME, "_save")
        save_button.click()

        # 2️⃣ Acceder al perfil del usuario para configurarlo como staff (si es necesario)
        if is_staff:
            user_link = wait.until(EC.presence_of_element_located((By.LINK_TEXT, username)))
            user_link.click()

            # Activar "Staff Status"
            staff_status_checkbox = wait.until(EC.presence_of_element_located((By.ID, "id_is_staff")))
            if not staff_status_checkbox.is_selected():
                staff_status_checkbox.click()

            # Asignar permisos (si se especificaron)
            if permission_to_assign:
                search_box = wait.until(EC.presence_of_element_located((By.ID, "id_user_permissions_input")))
                search_box.send_keys(permission_to_assign)  # Buscar el permiso
                permissions_section = wait.until(EC.presence_of_element_located((By.XPATH, f"//option[contains(text(), '{permission_to_assign}')]")))
                self.selenium.execute_script("arguments[0].scrollIntoView(true);", permissions_section)
                time.sleep(1)
                ActionChains(self.selenium).move_to_element(permissions_section).double_click(permissions_section).perform()

            # Guardar cambios
            final_save_button = self.selenium.find_element(By.NAME, "_save")
            final_save_button.click()
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".success")))

    def test_create_user_with_view_permission(self):
        """
        Test que verifica que un usuario con permiso 'Can view user'
        pueda ver pero no editar otros usuarios.
        """
        # 1️⃣ Login como superusuario
        self.admin_login("isard", "pirineus")

        # 2️⃣ Crear usuario staff con permiso 'Can view user'
        self.create_user_and_assign_permission(
            username="staff1",
            password="staffpass",
            permission_to_assign="Authentication and Authorization | user | Can view user",
            is_staff=True,
        )

        # 3️⃣ Crear tres usuarios normales sin permisos
        for i in range(1, 4):
            self.create_user_and_assign_permission(
                username=f"user{i}",
                password="userpass",
                is_staff=False,  # No necesitan acceso al admin
            )

        # 4️⃣ Cerrar sesión como superusuario
        self.admin_logout()

        # 5️⃣ Login como staff1
        self.admin_login("staff1", "staffpass")
        self.selenium.get(f"{self.live_server_url}/admin/auth/user/")
        wait = WebDriverWait(self.selenium, 15)

        # 6️⃣ Verificar que el usuario staff1 pueda ver pero no editar usuarios
        for i in range(1, 4):
            user_text = f"user{i}"
            try:
                row = wait.until(EC.presence_of_element_located((By.XPATH, f"//tr[contains(., '{user_text}')]")))
            except TimeoutException:
                assert False, f"El usuario {user_text} no se muestra en la lista."

            # Intentar editar al usuario y verificar que no se permite
            link = row.find_element(By.XPATH, f".//a[text()='{user_text}']")
            link.click()
            page_source = self.selenium.page_source.lower()
            if "permission" not in page_source and "forbid" not in page_source:
                assert False, f"Al hacer clic en {user_text}, no se muestra error de permisos. Página:\n{self.selenium.page_source}"
            self.selenium.get(f"{self.live_server_url}/admin/auth/user/")

        # 7️⃣ Cerrar sesión como staff1 al finalizar el test
        self.admin_logout()
