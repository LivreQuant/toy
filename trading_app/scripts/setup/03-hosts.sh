# Get Minikube IP
MINIKUBE_IP=$(minikube ip)

echo -e "\n============================================================"
echo "Setup complete! To access your application, you need to update your hosts file."
echo
echo "Run this command to add an entry to your hosts file:"
echo "    sudo sh -c \"echo '$MINIKUBE_IP trading.local' >> /etc/hosts\""
echo
echo "Or manually edit /etc/hosts with your preferred editor:"
echo "    sudo nano /etc/hosts"
echo "    sudo vim /etc/hosts"
echo
echo "Then add this line:"
echo "    $MINIKUBE_IP trading.local"
echo
echo "After updating your hosts file, you can access the application at:"
echo "    http://trading.local"
echo "============================================================"