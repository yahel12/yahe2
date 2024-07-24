if [ -z $UPSTREAM_REPO ]
then
  echo "Cloning main Repository"
  git clone https://github.com/yahel12/yahe2.git /yahe2
else
  echo "Cloning Custom Repo from $UPSTREAM_REPO "
  git clone $UPSTREAM_REPO /yahe2
fi
cd /yahe2
pip3 install -U -r requirements.txt
echo "Starting yahe2...."
python3 bot.py
