LOGIN_HTML = """<html>
                  <head></head>
                  <body>
                    <form method="post" action="/login">
                      <label><b>Username</b></label>
                      <input type="text" placeholder="Enter Username" name="username" required>
                      <label><b>Password</b></label>
                      <input type="password" placeholder="Enter Password" name="password" required>
                      <button type="submit">Login</button>
                    </form>
                  </body>
                </html>"""

LOGOUT_HTML = """<html>
                   <head></head>
                   <style>
                   button {background-color: transparent; text-decoration: underline; border: none; color: blue; cursor: pointer;}
                   </style>
                   <body>
                     <form method="post" action="/logout">
                       <button type="submit">Logout</button>
                     </form>
                   </body>
                 </html>"""
