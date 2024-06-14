if [ -z $UPSTREAM_REPO ]
then
  echo "Cloning main Repository"
  git clone https://github.com/Hislordshipb/Hislordshipb.git /DQ
else
  echo "Cloning Custom Repo from $UPSTREAM_REPO "
  git clone $UPSTREAM_REPO /Hislordshipb
fi
cd /Hislordshipb
pip3 install -U -r requirements.txt
echo "Starting Hislordshipb...."
python3 bot.py
